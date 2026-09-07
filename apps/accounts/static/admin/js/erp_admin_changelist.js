"use strict";

(() => {
    const labels = new Map([
        ["Active", "فعال"], ["Completed", "تکمیل‌شده"], ["Draft", "پیش‌نویس"],
        ["Terminated", "خاتمه‌یافته"], ["Approved", "تأییدشده"], ["Archived", "بایگانی‌شده"],
        ["Revised", "بازنگری‌شده"], ["Submitted", "ارسال‌شده"], ["Yes", "بله"],
        ["No", "خیر"], ["All", "همه"], ["Add", "افزودن"], ["Change", "ویرایش"],
        ["View", "مشاهده"], ["Search", "جست‌وجو"], ["Filter", "فیلترها"],
    ]);

    function localizeText(node) {
        const text = node.nodeValue;
        const trimmed = text.trim();
        if (!labels.has(trimmed)) return;
        node.nodeValue = text.replace(trimmed, labels.get(trimmed));
    }

    function localizeChangelist() {
        const changelist = document.getElementById("changelist");
        if (!changelist) return;
        const walker = document.createTreeWalker(changelist, NodeFilter.SHOW_TEXT);
        const textNodes = [];
        while (walker.nextNode()) textNodes.push(walker.currentNode);
        textNodes.forEach(localizeText);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", localizeChangelist, {once: true});
    } else {
        localizeChangelist();
    }
})();
