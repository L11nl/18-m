# ربط UOTP مع البوت

هذه النسخة تستخدم واجهة `handler_api` الخاصة بـ UOTP من خلال متغيرات البيئة، ولا تحفظ مفتاح API داخل الكود.

## إعداد Railway

أضف القيم التالية في **Railway → Variables**:

```env
UOTP_API_KEY=ضع_مفتاح_UOTP_الجديد_هنا
UOTP_BASE_URL=https://uotp.store/api/stubs/handler_api.php
UOTP_SERVICE=jiomart
UOTP_COUNTRY=22
UOTP_OPERATOR=
UOTP_OPERATORS=
UOTP_DELAY=2
```

- الخدمة: `jiomart`
- الدولة: الهند `22`
- `operator` اختياري؛ اتركه فارغاً ما لم يزوّدك دعم UOTP برمز محدد.
- لا تضع المفتاح الحقيقي في GitHub أو داخل ملف `.env.example`.

## الطلبات التي ينفذها البوت

### فحص الرصيد

```text
action=getBalance
```

الاستجابة الناجحة:

```text
ACCESS_BALANCE:123.45
```

### شراء رقم

```text
action=getNumber&service=jiomart&country=22
```

الاستجابة الناجحة:

```text
ACCESS_NUMBER:ACTIVATION_ID:PHONE_NUMBER
```

بعد الشراء يرسل البوت `setStatus=1` لتأكيد أن مستلم الرسالة جاهز.

### متابعة كود SMS

```text
action=getStatus&id=ACTIVATION_ID
```

أهم الاستجابات:

```text
STATUS_WAIT_CODE
STATUS_WAIT_RESEND
STATUS_CANCEL
STATUS_OK:123456
```

### تغيير حالة التفعيل

- `1`: الرقم جاهز لاستلام الرسالة.
- `3`: طلب كود جديد.
- `6`: إكمال التفعيل.
- `8`: إلغاء التفعيل.

## التشغيل من بوت تيليجرام

1. افتح `/sniper`.
2. اختر `UOTP` فقط في أول اختبار.
3. اختر السرعة العادية وحجم دفعة `1`.
4. راقب `/logs` لمعرفة رد API الحقيقي.
5. استخدم `/orders` لرؤية الرقم، معرف التفعيل، حالة الانتظار والكود عند وصوله.

يعرض السجل أخطاء UOTP بدلاً من تجاهلها، ومنها:

```text
BAD_KEY
BAD_SERVICE
BAD_COUNTRY
BAD_OPERATOR
NO_BALANCE
NO_NUMBERS
ACCOUNT_BAN
NO_CONNECTION
ERROR_DATABASE
```
