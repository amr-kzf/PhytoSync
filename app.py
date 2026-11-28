import os
import random
import math
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
import requests
from flask import Flask, abort, redirect, request, url_for, render_template, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from localization import AR_TRANSLATIONS, current_language, translate_text

load_dotenv()

# ================= CONFIG & EXTENSIONS =================
from config import Config
from extensions import db, mail

# ================= APP INIT =================
app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
mail.init_app(app)

@app.context_processor
def inject_language_context():
    language = current_language(session.get("language"))
    return {
        "site_language": language,
        "translate": lambda value: translate_text(value, language),
        "language_translations": AR_TRANSLATIONS,
    }

# ================= MODELS =================
from models import User, Otp, Answer, Topic, CropStandard, UserCrop, CropLog

# ================= BLUEPRINTS =================
from chatbot import chatbot_bp
from crop_prediction import crop_prediction_bp
from crop_tracking import crop_tracking_bp
from auth import auth_bp
from community import community_bp, give_daily_bonus
from disease_detection import disease_bp

app.register_blueprint(chatbot_bp)
app.register_blueprint(crop_prediction_bp)
app.register_blueprint(crop_tracking_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(community_bp)
app.register_blueprint(disease_bp)

from utils.avtar import get_initials


# ================= INITIALIZE DB & SEED DATA =================
with app.app_context():
    db.create_all()
    try:
        from sqlalchemy import text
        with db.engine.connect() as conn:
            if "sqlite" not in str(db.engine.url):
                conn.execute(text("""
                    ALTER TABLE crop_logs ADD COLUMN IF NOT EXISTS disease_label VARCHAR(100);
                    ALTER TABLE crop_logs ADD COLUMN IF NOT EXISTS disease_confidence FLOAT;
                    ALTER TABLE crop_logs ADD COLUMN IF NOT EXISTS disease_precautions_json TEXT;
                    ALTER TABLE crop_logs ADD COLUMN IF NOT EXISTS disease_status VARCHAR(50) DEFAULT 'active';
                """))
                conn.commit()
    except Exception:
        pass

    try:
        # Check if CropStandards are seeded
        if CropStandard.query.count() == 0:
            from seed_crops import seed_database
            seed_database()
        
        # Keep the bundled showcase account aligned with the Egypt-focused demo.
        # This updates only the known local demo records; normal registered users are untouched.
        from seed_demo_data import seed_demo_platform
        seed_demo_platform()
    except Exception as e:
        print(f"[PhytoSync Warning] Seed database check: {e}")


# ================= ROUTES =================
@app.route("/")
def home():
    return render_template("HomePage/home_page.html")


@app.route("/set-language", methods=["POST"])
def set_language():
    language = request.form.get("language")
    if language not in {"en", "ar"}:
        abort(400)

    session["language"] = language
    referrer = request.referrer
    if referrer:
        parsed_referrer = urlsplit(referrer)
        if not parsed_referrer.netloc or parsed_referrer.netloc == request.host:
            return redirect(referrer)
    return redirect(url_for("home"))


# ---------------- DEMO LOGIN ----------------
@app.route("/demo-login")
def demo_login():
    demo_user = User.query.filter_by(email="demo@phytosync.app").first()
    if not demo_user:
        from seed_demo_data import seed_demo_platform
        seed_demo_platform()
        demo_user = User.query.filter_by(email="demo@phytosync.app").first()

    session["user_id"] = demo_user.user_id
    session["full_name"] = demo_user.full_name
    session["initials"] = get_initials(demo_user.full_name)
    session["location"] = demo_user.location
    session["badge"] = demo_user.badge
    give_daily_bonus(demo_user.user_id)
    flash(f"Welcome back, {demo_user.full_name}! 🌾", "success")
    return redirect(url_for("crop_tracking.crop_tracking"))


# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    now = datetime.now()
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        
        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password_hash, password):
            if not user.is_verified:
                Otp.query.filter_by(
                    user_id=user.user_id,
                    is_used=False
                ).update({"is_used": True})

                generated_otp = str(random.randint(100000, 999999))
                otp = Otp(
                    user_id=user.user_id,
                    otp_code=generated_otp,
                    expires_at=now + timedelta(minutes=10),
                    is_used=False
                )
                db.session.add(otp)
                db.session.commit()

                from utils.mailer import send_otp_email
                send_otp_email(user.email, generated_otp, user.full_name)
                return redirect(url_for("verify_otp", user_id=user.user_id))

            session["user_id"] = user.user_id
            session["full_name"] = user.full_name
            session["initials"] = get_initials(user.full_name)
            session["location"] = user.location
            session["badge"] = user.badge
            give_daily_bonus(user.user_id)
            
            flash(f"Welcome back, {user.full_name}! 🌾", "success")
            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "danger")
        return redirect(url_for('login'))

    return render_template("Login/login.html")


# ---------------- DASHBOARD ----------------
def _stormglass_numeric_value(hour, parameter):
    sources = hour.get(parameter)
    if not isinstance(sources, dict):
        raise ValueError(f"Stormglass response is missing {parameter}.")

    for value in [sources.get("sg"), *sources.values()]:
        if value is None:
            continue
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(numeric_value):
            return numeric_value

    raise ValueError(f"Stormglass returned no valid {parameter} value.")


def _fetch_stormglass_weather(city, api_key):
    geocoding_response = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": city, "count": 1, "language": "en", "format": "json"},
        timeout=4,
    )
    geocoding_response.raise_for_status()
    geocoding_data = geocoding_response.json()
    results = geocoding_data.get("results") if isinstance(geocoding_data, dict) else None
    if not isinstance(results, list) or not results:
        raise ValueError("The profile location could not be geocoded.")

    try:
        latitude = float(results[0]["latitude"])
        longitude = float(results[0]["longitude"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("The geocoder returned invalid coordinates.") from exc
    if not math.isfinite(latitude) or not -90 <= latitude <= 90:
        raise ValueError("The geocoder returned an invalid latitude.")
    if not math.isfinite(longitude) or not -180 <= longitude <= 180:
        raise ValueError("The geocoder returned an invalid longitude.")

    current_hour = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start = int(current_hour.timestamp())
    weather_response = requests.get(
        "https://api.stormglass.io/v2/weather/point",
        params={
            "lat": latitude,
            "lng": longitude,
            "params": "airTemperature,humidity,cloudCover,precipitation",
            "source": "sg",
            "start": start,
            "end": start + 3 * 60 * 60,
        },
        headers={"Authorization": api_key},
        timeout=4,
    )
    weather_response.raise_for_status()
    weather_data = weather_response.json()
    hours = weather_data.get("hours") if isinstance(weather_data, dict) else None
    if not isinstance(hours, list) or not hours:
        raise ValueError("Stormglass returned no forecast hours.")
    if not isinstance(hours[0], dict):
        raise ValueError("Stormglass returned an invalid forecast hour.")

    hour = hours[0]
    temperature = _stormglass_numeric_value(hour, "airTemperature")
    humidity = _stormglass_numeric_value(hour, "humidity")
    cloud_cover = _stormglass_numeric_value(hour, "cloudCover")
    precipitation = _stormglass_numeric_value(hour, "precipitation")
    if not 0 <= humidity <= 100 or not 0 <= cloud_cover <= 100:
        raise ValueError("Stormglass returned an invalid percentage value.")

    if precipitation > 0.1:
        description = "Rain likely"
    elif cloud_cover >= 85:
        description = "Overcast"
    elif cloud_cover >= 40:
        description = "Partly cloudy"
    else:
        description = "Clear"

    return {
        "temp": round(temperature),
        "humidity": round(humidity),
        "description": description,
        "source": "live",
    }


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_record = User.query.get(session["user_id"])
    if not user_record:
        session.clear()
        return redirect(url_for("login"))

    if not user_record.is_verified:
        return redirect(url_for("verify_otp", user_id=user_record.user_id))

    api_key = os.getenv("STORMGLASS_API_KEY")
    # Keep the default weather context aligned with the Egyptian AgriTech demo.
    city = user_record.location or "Cairo, Egypt"

    weather_data = None
    if api_key and city:
        try:
            weather_data = _fetch_stormglass_weather(city, api_key)
        except (requests.RequestException, ValueError, TypeError, KeyError) as exc:
            app.logger.warning(
                "Weather lookup failed (%s); showing sample weather.",
                type(exc).__name__,
            )

    if not weather_data:
        weather_data = {
            "temp": 28,
            "humidity": 65,
            "description": "Clear Sky / Mild Sunshine",
            "source": "sample"
        }

    farms = (
        UserCrop.query
        .filter_by(user_id=user_record.user_id)
        .order_by(UserCrop.created_at.desc())
        .all()
    )
    farm_ids = [farm.user_crop_id for farm in farms]
    recent_logs = []
    if farm_ids:
        recent_logs = (
            CropLog.query
            .filter(CropLog.user_crop_id.in_(farm_ids))
            .order_by(CropLog.log_date.desc(), CropLog.crop_log_id.desc())
            .limit(6)
            .all()
        )

    active_disease_logs = [
        log for log in recent_logs
        if log.disease_label and log.disease_status not in ("healthy", "treated")
    ]

    return render_template(
        "Dashboard/dashboard.html",
        user=user_record,
        weather=weather_data,
        farms=farms,
        recent_logs=recent_logs,
        active_disease_logs=active_disease_logs
    )


# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    flash("You have been safely logged out.", "info")
    return redirect(url_for("login"))


# ---------------- OTP VERIFY ----------------
@app.route("/verify-otp/<int:user_id>", methods=["GET", "POST"])
def verify_otp(user_id):
    if request.method == "POST":
        entered_otp = request.form.get("otp", "").strip()
        now = datetime.now()

        otp_record = (
            Otp.query
            .filter(
                Otp.user_id == user_id,
                Otp.is_used == False
            )
            .order_by(Otp.created_at.desc())
            .first()
        )

        if not otp_record or otp_record.otp_code != entered_otp:
            return render_template(
                "Otp/verify_otp.html",
                error="Invalid OTP code. Please check and retry.",
                user_id=user_id
            )

        if otp_record.expires_at < now:
            return render_template(
                "Otp/verify_otp.html",
                error="OTP has expired. Please click Resend OTP.",
                user_id=user_id
            )

        otp_record.is_used = True
        user = User.query.get(user_id)
        if user:
            user.is_verified = True
            db.session.commit()
            session["user_id"] = user.user_id
            session["full_name"] = user.full_name
            session["initials"] = get_initials(user.full_name)
            session["location"] = user.location
            session["badge"] = user.badge
            give_daily_bonus(user.user_id)
            flash("Account verified successfully! Welcome to PhytoSync.", "success")
            return redirect(url_for("dashboard"))

        return redirect(url_for("login"))

    return render_template("Otp/verify_otp.html", user_id=user_id)


# ---------------- RESEND OTP ----------------
@app.route("/resend-otp/<int:user_id>")
def resend_otp(user_id):
    user = User.query.get(user_id)
    if not user:
        flash("Invalid user request.", "danger")
        return redirect(url_for("login"))
    
    if user.is_verified:
        return redirect(url_for("login"))

    Otp.query.filter_by(user_id=user_id, is_used=False).update(
        {"is_used": True}
    )

    now = datetime.now()
    new_otp = str(random.randint(100000, 999999))
    otp = Otp(
        user_id=user_id,
        otp_code=new_otp,
        expires_at=now + timedelta(minutes=10),
        is_used=False
    )

    db.session.add(otp)
    db.session.commit()

    from utils.mailer import send_otp_email
    send_otp_email(user.email, new_otp, user.full_name)
    flash("A new verification code has been dispatched to your email.", "info")
    return redirect(url_for("verify_otp", user_id=user_id))


# ---------------- REGISTER ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        location = request.form.get("location", "").strip()
        dob_str = request.form.get("dob", "")
        mobile = request.form.get("mobile", "").strip()

        if User.query.filter_by(email=email).first():
            flash("Email address is already registered. Please login.", "warning")
            return redirect(url_for("login"))

        dob_val = None
        if dob_str:
            try:
                dob_val = datetime.strptime(dob_str, "%Y-%m-%d").date()
            except ValueError:
                dob_val = None

        user = User(
            full_name=full_name,
            email=email,
            password_hash=generate_password_hash(password),
            role="FARMER",
            points=10,  # Welcome bonus points
            lifetime_points=10,
            badge="Beginner",
            location=location,
            dob=dob_val,
            mobile=mobile,
            is_verified=False,
            created_at=datetime.now()
        )

        db.session.add(user)
        db.session.commit()

        otp_code = str(random.randint(100000, 999999))
        otp = Otp(
            user_id=user.user_id,
            otp_code=otp_code,
            expires_at=datetime.now() + timedelta(minutes=10),
            is_used=False
        )

        db.session.add(otp)
        db.session.commit()

        from utils.mailer import send_otp_email
        send_otp_email(user.email, otp_code, user.full_name)
        flash("Registration successful! Please verify your OTP.", "success")
        return redirect(url_for("verify_otp", user_id=user.user_id))
    
    return render_template("Login/login.html")


# ---------------- PROFILE & BADGES ----------------
BADGE_ORDER = [
    ("Beginner", 0),
    ("Contributor", 50),
    ("Trusted Farmer", 150),
    ("Expert Farmer", 300),
]

def get_next_badge_info(lifetime_points):
    for badge, points in BADGE_ORDER:
        if lifetime_points < points:
            return badge, points
    return "Max Level (Expert Farmer)", None


@app.route("/profile")
def profile():
    if "user_id" not in session:
        return redirect(url_for("login"))
    
    user = User.query.get(session["user_id"])
    if not user:
        return redirect(url_for("login"))

    question_count = Topic.query.filter_by(user_id=user.user_id).count()
    answers_count = Answer.query.filter_by(user_id=user.user_id).count()
    best_answers_count = Answer.query.filter_by(
        user_id=user.user_id,
        is_best_solution=True
    ).count()
    next_badge, next_badge_points = get_next_badge_info(user.lifetime_points)

    return render_template(
        "Profile/profile.html",
        user=user,
        question_count=question_count,
        answers_count=answers_count,
        best_answers_count=best_answers_count,
        next_badge=next_badge,
        next_badge_points=next_badge_points
    )


# ================= RUN =================
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5144)
