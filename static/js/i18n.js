(() => {
    const config = window.PHYTOSYNC_I18N || {};
    const language = config.language === 'ar' ? 'ar' : 'en';
    const translations = config.translations || {};
    const cropNames = {
        Apple: 'تفاح',
        Blueberry: 'توت أزرق',
        Cherry: 'كرز',
        'Corn (maize)': 'ذرة',
        Corn: 'ذرة',
        Grape: 'عنب',
        Orange: 'برتقال',
        Peach: 'خوخ',
        Pepper: 'فلفل',
        Potato: 'بطاطس',
        Raspberry: 'توت العليق',
        Soybean: 'فول الصويا',
        Squash: 'قرع',
        Strawberry: 'فراولة',
        Tomato: 'طماطم'
    };
    const conditions = {
        Apple_scab: 'جرب التفاح',
        Black_rot: 'العفن الأسود',
        Cedar_apple_rust: 'صدأ التفاح',
        healthy: 'سليم',
        Powdery_mildew: 'البياض الدقيقي',
        'Cercospora_leaf_spot Gray_leaf_spot': 'تبقع الأوراق والسركسبورا',
        Common_rust: 'الصدأ الشائع',
        Northern_Leaf_Blight: 'لفحة الأوراق الشمالية',
        Black_Measles: 'الحصبة السوداء',
        'Leaf_blight (Isariopsis Leaf Spot)': 'لفحة الأوراق',
        Haunglongbing: 'اخضرار الحمضيات',
        Bacterial_spot: 'التبقع البكتيري',
        Early_blight: 'اللفحة المبكرة',
        Late_blight: 'اللفحة المتأخرة',
        Leaf_Mold: 'عفن الأوراق',
        Septoria_leaf_spot: 'تبقع أوراق السبتوريا',
        'Spider_mites Two-spotted spider mite': 'العنكبوت الأحمر ذو البقعتين',
        Target_Spot: 'التبقع الهدف',
        Tomato_Yellow_Leaf_Curl_Virus: 'فيروس تجعد واصفرار أوراق الطماطم',
        Tomato_mosaic_virus: 'فيروس موزاييك الطماطم',
        Esca: 'مرض الإيسكا'
    };

    function translateModelLabel(value) {
        const parts = value.split('___');
        if (parts.length !== 2) return value;
        const crop = parts[0].replaceAll('_', ' ').replace(/\s*\(maize\)/i, ' (maize)');
        const condition = parts[1].replace(/_+/g, '_').replace(/\s+/g, ' ').trim();
        const cropLabel = cropNames[crop] || cropNames[parts[0]] || crop;
        const conditionLabel = conditions[condition] || condition.replaceAll('_', ' ');
        return `${cropLabel} — ${conditionLabel}`;
    }

    function translateText(value) {
        if (language !== 'ar' || !value) return value;
        if (translations[value] !== undefined) return translations[value];

        if (value.includes('___')) return translateModelLabel(value);

        const unexpectedResponse = value.match(/^PhytoSync returned an unexpected response \(HTTP (\d+)\)\. Check the server terminal for errors\.$/);
        if (unexpectedResponse) return `أعاد PhytoSync استجابة غير متوقعة (HTTP ${unexpectedResponse[1]}). راجع سجل الخادم لمعرفة الخطأ.`;
        const failedResponse = value.match(/^PhytoSync AI couldn't respond \(HTTP (\d+)\)\. Please try again\.$/);
        if (failedResponse) return `تعذر على مساعد PhytoSync الرد (HTTP ${failedResponse[1]}). حاول مجددًا.`;

        let match = value.match(/^Good (morning|day), (.+)$/);
        if (match) return `${match[1] === 'morning' ? 'صباح الخير' : 'مرحبًا'}، ${match[2]}`;
        match = value.match(/^(\d+) active farms?$/);
        if (match) return `${match[1]} مزرعة نشطة`;
        match = value.match(/^(\d+) Topics?$/);
        if (match) return `${match[1]} موضوع`;
        match = value.match(/^(\d+(?:\.\d+)?) pts$/);
        if (match) return `${match[1]} نقطة`;
        match = value.match(/^Locked • Need (\d+) more answers$/);
        if (match) return `مغلق • تحتاج إلى ${match[1]} إجابة إضافية`;
        match = value.match(/^Locked • Need (\d+) points$/);
        if (match) return `مغلق • تحتاج إلى ${match[1]} نقطة`;
        match = value.match(/^(.+) value should be between (\d+(?:\.\d+)?) and (\d+(?:\.\d+)?)!$/);
        if (match) {
            const field = translations[match[1]] || match[1];
            return `يجب أن تكون قيمة ${field} بين ${match[2]} و${match[3]}.`;
        }
        match = value.match(/^Moderate \(([\d.]+) - ([\d.]+) mm\)$/);
        if (match) return `متوسط (${match[1]} - ${match[2]} مم)`;
        match = value.match(/^Week (\d+)$/);
        if (match) return `الأسبوع ${match[1]}`;
        match = value.match(/^(\d+(?:\.\d+)?)% Match$/);
        if (match) return `مطابقة بنسبة ${match[1]}٪`;
        match = value.match(/^(\d+)% Confident$/);
        if (match) return `مستوى الثقة ${match[1]}٪`;
        match = value.match(/^Score: (\d+)$/);
        if (match) return `النتيجة: ${match[1]}`;
        match = value.match(/^Score: (\d+)\/100$/);
        if (match) return `النتيجة: ${match[1]} من 100`;
        match = value.match(/^(\d+) pts$/);
        if (match) return `${match[1]} نقطة`;
        match = value.match(/^Conditioned: (.+)$/);
        if (match) return `تم تخصيص التحليل لمحصول ${cropNames[match[1]] || match[1]}`;
        match = value.match(/^Diagnose for (.+)$/);
        if (match) return `شخّص على أساس ${cropNames[match[1]] || match[1]}`;

        return value;
    }

    function translateTextNode(node) {
        const parent = node.parentElement;
        if (!parent || parent.closest('script, style, noscript, textarea, input, [data-no-translate]')) return;
        const source = node.nodeValue;
        const text = source.trim().replace(/\s+/g, ' ');
        if (!text) return;
        const translated = translateText(text);
        if (translated !== text) {
            const leading = source.match(/^\s*/)[0];
            const trailing = source.match(/\s*$/)[0];
            node.nodeValue = `${leading}${translated}${trailing}`;
        }
    }

    function translateElement(element) {
        if (element.nodeType === Node.TEXT_NODE) {
            translateTextNode(element);
            return;
        }
        if (element.nodeType !== Node.ELEMENT_NODE) return;
        ['placeholder', 'title', 'aria-label', 'alt'].forEach(attribute => {
            const value = element.getAttribute(attribute);
            if (value) element.setAttribute(attribute, translateText(value));
        });
        element.childNodes.forEach(translateElement);
    }

    function applyTranslations(root = document.body) {
        if (language !== 'ar') return;
        translateElement(root);
        const title = document.querySelector('head title');
        if (title) title.textContent = translateText(title.textContent.trim());
    }

    window.PhytoSyncI18n = {
        language,
        translate: translateText
    };

    if (language === 'ar') {
        applyTranslations(document.body);
        const observer = new MutationObserver(records => {
            records.forEach(record => {
                if (record.type === 'characterData') {
                    translateTextNode(record.target);
                } else {
                    record.addedNodes.forEach(translateElement);
                }
            });
        });
        observer.observe(document.body, { childList: true, characterData: true, subtree: true });
    }
})();
