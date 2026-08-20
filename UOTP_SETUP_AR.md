# إعداد UOTP — الهند / JioMart

أضف المتغيرات التالية في Railway > Variables:

```env
UOTP_API_KEY=ضع_المفتاح_الجديد_هنا
UOTP_BASE_URL=https://uotp.store/api/stubs/handler_api.php
UOTP_SERVICE=jiomart
UOTP_COUNTRY=22
UOTP_OPERATOR=
UOTP_OPERATORS=
UOTP_DELAY=2
```

لا تضع المفتاح داخل ملفات المشروع. بعد حفظ المتغيرات نفّذ Redeploy.

## طريقة التشغيل من البوت

1. افتح `/sniper`.
2. فعّل مزود `UOTP` فقط للاختبار الأول.
3. اختر السرعة العادية ودفعة `1`.
4. بعد التشغيل راقب `/logs` و`/orders`.

سيعرض السجل رد API الحقيقي، مثل:

- `NO_NUMBERS`
- `NO_BALANCE`
- `BAD_SERVICE`
- `BAD_COUNTRY`
- `BAD_KEY`
- `ACCESS_NUMBER:...`

## دورة التفعيل المستخدمة

- شراء رقم: `getNumber` بخدمة `jiomart` والدولة `22`.
- تأكيد جاهزية الرقم: `setStatus=1`.
- متابعة الرسالة: `getStatus`.
- طلب رمز جديد: `setStatus=3`.
- إكمال التفعيل: `setStatus=6`.
- إلغاء التفعيل: `setStatus=8`.
