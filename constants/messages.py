"""
تمام پیام‌های کاربرپسند ربات در این فایل متمرکز شده‌اند.
هیچ متن بلندی نباید مستقیماً داخل هندلرها قرار گیرد.
"""

# ──────────────────────────────
# Start
# ──────────────────────────────

WELCOME: str = (
    "سلام {first_name} 👋\n\n"
    "به ربات عضویت VIP خوش آمدید.\n\n"
    "از منوی زیر گزینه موردنظر خود را انتخاب کنید."
)

# ──────────────────────────────
# UID
# ──────────────────────────────

ASK_UID: str = (
    "⭐ برای فعال‌سازی عضویت VIP مراحل زیر را انجام دهید:\n\n"
    "1️⃣ ابتدا از طریق لینک زیر در صرافی Yubit ثبت‌نام کنید:\n"
    "🔗 {register_link}\n\n"
    "2️⃣ مجموع موجودی حساب شما باید حداقل "
    "{min_balance} USDT باشد.\n\n"
    "3️⃣ سپس UID حساب Yubit خود را ارسال کنید.\n\n"
    "🆔 لطفاً UID خود را وارد کنید:"
)

CHECKING: str = "⏳ در حال بررسی اطلاعات..."

MY_TELEGRAM_ID: str = "Telegram User ID شما:\n{telegram_id}"

UID_INVALID: str = (
    "❌ UID نامعتبر است.\n\n"
    "UID باید بین {min_length} تا {max_length} رقم "
    "و فقط شامل اعداد باشد.\n\n"
    "لطفاً UID صحیح خود را ارسال کنید."
)

UID_IN_USE: str = (
    "❌ این UID قبلاً برای حساب دیگری ثبت شده است.\n\n"
    "اگر فکر می‌کنید اشتباه شده، با پشتیبانی تماس بگیرید."
)

# ──────────────────────────────
# Validation Errors
# ──────────────────────────────

VALIDATION_FAILED: str = (
    "❌ امکان تأیید حساب وجود ندارد.\n\n"
    "مطمئن شوید:\n"
    "• با لینک ما ثبت‌نام کرده باشید.\n"
    "• UID را صحیح وارد کرده باشید."
)

INSUFFICIENT_BALANCE: str = (
    "❌ موجودی شما کافی نیست.\n\n"
    "حداقل موجودی لازم:\n"
    "{min_balance} USDT\n\n"
    "موجودی فعلی:\n"
    "{balance} USDT"
)

# ──────────────────────────────
# Already VIP
# ──────────────────────────────

ALREADY_VIP: str = (
    "✅ شما قبلاً عضو VIP شده‌اید.\n\n"
    "نیازی به ثبت‌نام مجدد نیست.\n"
    "برای مشاهده وضعیت حساب از منو استفاده کنید."
)

INVITE_RESENT: str = (
    "✅ عضویت VIP شما فعال است.\n\n"
    "لینک ورود جدید:\n"
    "{invite_link}"
)

# ──────────────────────────────
# Success
# ──────────────────────────────

REGISTRATION_SUCCESS: str = (
    "✅ حساب شما تأیید شد.\n\n"
    "━━━━━━━━━━━━━━\n"
    "🆔 UID\n"
    "{uid}\n\n"
    "💰 موجودی\n"
    "{balance} USDT\n"
    "━━━━━━━━━━━━━━\n\n"
    "{warning_text}"
    "🔗 لینک ورود VIP\n"
    "{invite_link}"
)

WARNING_TEXT: str = (
    "⚠️ توجه:\n\n"
    "موجودی شما در محدوده هشدار قرار دارد.\n\n"
    "اگر موجودی شما به زیر {min_balance} USDT برسد، "
    "دسترسی VIP شما حذف خواهد شد.\n\n"
)

# ──────────────────────────────
# Status
# ──────────────────────────────

NOT_VIP: str = "❌ شما هنوز عضو VIP نیستید ❌"

STATUS_INFO: str = (
    "👤 اطلاعات حساب\n\n"
    "━━━━━━━━━━━━━━\n"
    "🆔 UID\n"
    "{uid}\n\n"
    "💰 آخرین موجودی\n"
    "{balance} USDT\n\n"
    "📌 وضعیت\n"
    "{status}\n\n"
    "⚠️ تعداد هشدارها\n"
    "{warning_count}\n"
    "━━━━━━━━━━━━━━"
)

# ──────────────────────────────
# Campaign
# ──────────────────────────────

CAMPAIGN_EMPTY: str = (
    "در حال حاضر رویداد یا کمپینی در جریان نیست."
)

# ──────────────────────────────
# Support
# ──────────────────────────────

SUPPORT_PROMPT: str = (
    "☎️ پیام خود را برای پشتیبانی ارسال کنید.\n\n"
    "می‌توانید متن، عکس، ویدیو، فایل یا پیام فورواردشده بفرستید."
)

SUPPORT_RECEIVED: str = (
    "✅ پیام شما برای پشتیبانی ارسال شد.\n"
    "پاسخ از همین ربات برای شما ارسال خواهد شد."
)

SUPPORT_ADMIN_HEADER: str = (
    "📨 پیام جدید پشتیبانی\n\n"
    "نام: {first_name}\n"
    "نام کاربری: {username}\n"
    "Telegram ID: {telegram_id}\n\n"
    "برای پاسخ، روی پیام بعدی Reply کنید."
)

SUPPORT_REPLY_HEADER: str = "📨 پاسخ پشتیبانی:"

SUPPORT_DELIVERY_FAILED: str = (
    "⚠️ ارسال پیام به پشتیبانی انجام نشد. لطفاً کمی بعد تلاش کنید."
)

# ──────────────────────────────
# Register
# ──────────────────────────────

REGISTER_MSG: str = (
    "🎩\n\n"
    "لینک ثبت‌نام:\n"
    "{register_link}"
)

# ──────────────────────────────
# Scheduler Notifications
# ──────────────────────────────

KICK_MSG: str = (
    "❌ عضویت VIP شما غیرفعال شد.\n\n"
    "━━━━━━━━━━━━━━\n"
    "💰 موجودی فعلی:\n"
    "{balance} USDT\n\n"
    "حداقل موجودی لازم:\n"
    "{min_balance} USDT\n"
    "━━━━━━━━━━━━━━\n\n"
    "در صورت افزایش موجودی "
    "می‌توانید دوباره عضو VIP شوید."
)

WARNING_MSG: str = (
    "⚠️ هشدار کاهش موجودی\n\n"
    "━━━━━━━━━━━━━━\n"
    "💰 موجودی فعلی:\n"
    "{balance} USDT\n"
    "━━━━━━━━━━━━━━\n\n"
    "حداقل موجودی:\n"
    "{min_balance} USDT\n\n"
    "اگر موجودی شما به زیر {min_balance} برسد، "
    "دسترسی VIP به صورت خودکار حذف خواهد شد.\n\n"
    "لطفاً موجودی خود را افزایش دهید."
)

# ──────────────────────────────
# Generic Errors
# ──────────────────────────────

ERROR_GENERIC: str = (
    "⚠️ خطایی رخ داد. لطفاً کمی بعد دوباره تلاش کنید."
)

ERROR_API: str = (
    "⚠️ ارتباط با سرور برقرار نشد. لطفاً بعداً تلاش کنید."
)

ERROR_DB: str = (
    "⚠️ مشکل در پایگاه داده. لطفاً بعداً تلاش کنید."
)

# ──────────────────────────────
# Admin Panel
# ──────────────────────────────

ADMIN_WELCOME: str = (
    "مدیریت ربات\n\n"
    "از گزینه‌های زیر برای مشاهده آمار و مدیریت استفاده کنید."
)

ADMIN_STATS: str = (
    "آمار ربات\n\n"
    "کل کاربران ربات: {total_bot_users}\n"
    "کل رکوردهای VIP: {total_vip_records}\n"
    "VIP فعال: {active_vips}\n"
    "VIP غیرفعال: {inactive_vips}\n"
    "مجموع موجودی ثبت‌شده VIPهای فعال: {active_balance_total} USDT\n"
    "مجموع هشدارها: {total_warnings}\n"
    "آخرین بررسی ثبت‌شده: {latest_check}"
)

ADMIN_REFRESH_STARTED: str = (
    "در حال دریافت موجودی لحظه‌ای تمام VIPهای فعال..."
)

ADMIN_REFRESH_SUMMARY: str = (
    "چک لحظه‌ای تمام شد.\n\n"
    "موفق: {checked}\n"
    "ناموفق: {failed}\n"
    "کمتر از حداقل: {below_minimum}\n\n"
    "این عملیات فقط موجودی‌ها را به‌روزرسانی کرد و کسی را اخراج نکرد."
)

ADMIN_SEARCH_PROMPT: str = (
    "Telegram ID یا UID کاربر را ارسال کنید."
)

ADMIN_USER_NOT_FOUND: str = "کاربری با این مشخصات پیدا نشد."

ADMIN_USER_INFO: str = (
    "اطلاعات کاربر\n\n"
    "Telegram ID: {telegram_id}\n"
    "Username: {username}\n"
    "نام: {first_name}\n"
    "UID: {uid}\n"
    "وضعیت: {status}\n"
    "موجودی ذخیره‌شده: {stored_balance} USDT\n"
    "موجودی لحظه‌ای: {live_balance} USDT\n"
    "آخرین بررسی: {last_check}\n"
    "تعداد هشدار: {warning_count}"
)

ADMIN_BROADCAST_PROMPT: str = (
    "📢 محتوای همگانی را ارسال کنید\n\n"
    "✅ پشتیبانی کامل از:\n"
    "• متن\n"
    "• عکس\n"
    "• ویدیو\n"
    "• گیف\n"
    "• فایل\n"
    "• استیکر\n"
    "• پیام فوروارد شده\n\n"
    "⚡️ دقیقا همان پیام برای همه کاربران ارسال خواهد شد."
)

ADMIN_BROADCAST_PREVIEW: str = (
    "پیش‌نمایش پیام بالا نمایش داده شد.\n"
    "آیا برای همه کاربران ارسال شود؟"
)

ADMIN_BROADCAST_STARTED: str = (
    "ارسال پیام همگانی شروع شد. لطفاً صبر کنید..."
)

ADMIN_BROADCAST_RESULT: str = (
    "ارسال پیام همگانی تمام شد.\n\n"
    "کل گیرندگان: {total}\n"
    "موفق: {sent}\n"
    "ناموفق: {failed}"
)

ADMIN_CANCELLED: str = "عملیات لغو شد."
ADMIN_ACCESS_DENIED: str = "شما اجازه دسترسی به این بخش را ندارید."

ADMIN_ADD_PROMPT: str = (
    "برای افزودن VIP، اطلاعات را در یک پیام با این قالب بفرستید:\n\n"
    "TelegramID UID\n\n"
    "مثال:\n"
    "123456789 12345678\n\n"
    "کاربر باید قبلاً ربات را Start کرده باشد."
)

ADMIN_ADD_USER_UNKNOWN: str = (
    "این Telegram ID هنوز ربات را Start نکرده است."
)

ADMIN_ADD_SUCCESS: str = (
    "کاربر با موفقیت VIP شد.\n\n"
    "Telegram ID: {telegram_id}\n"
    "UID: {uid}\n"
    "موجودی: {balance} USDT\n"
    "نتیجه ارسال لینک: {delivery}"
)

ADMIN_VIP_INVITATION: str = (
    "عضویت VIP شما توسط ادمین فعال شد.\n\n"
    "UID: {uid}\n"
    "موجودی: {balance} USDT\n\n"
    "لینک یک‌بارمصرف ورود به کانال:\n"
    "{invite_link}"
)

ADMIN_REMOVE_PROMPT: str = (
    "Telegram ID یا UID کاربری که باید از VIP حذف شود را ارسال کنید."
)

ADMIN_REMOVE_CONFIRM: str = (
    "آیا این کاربر از کانال اخراج و VIP او غیرفعال شود؟\n\n"
    "Telegram ID: {telegram_id}\n"
    "Username: {username}\n"
    "UID: {uid}\n"
    "وضعیت فعلی: {status}\n"
    "موجودی ذخیره‌شده: {balance} USDT"
)

ADMIN_REMOVE_SUCCESS: str = (
    "کاربر از کانال اخراج و VIP او غیرفعال شد."
)

ADMIN_REMOVE_FAILED: str = (
    "اخراج کاربر یا باطل‌کردن لینک انجام نشد؛ وضعیت دیتابیس تغییر نکرد."
)

ADMIN_REMOVED_USER_NOTICE: str = (
    "عضویت VIP شما توسط ادمین غیرفعال شد."
)

ADMIN_EXPORT_EMPTY: str = "هیچ رکورد VIP برای خروجی وجود ندارد."

ADMIN_EXPORT_CAPTION: str = (
    "خروجی تمام VIPهای فعال و غیرفعال\n"
    "تعداد رکوردها: {count}"
)

ADMIN_CAMPAIGN_PROMPT: str = (
    "🎁 محتوای کمپین را ارسال کنید.\n\n"
    "متن، عکس، ویدیو، گیف، فایل و پیام فورواردشده پشتیبانی می‌شود."
)

ADMIN_CAMPAIGN_SAVED: str = (
    "✅ کمپین ذخیره شد و از منوی کاربران قابل مشاهده است."
)

ADMIN_INVITE_CREATED: str = (
    "✅ لینک یکبارمصرف ساخته شد:\n\n"
    "{invite_link}"
)

ADMIN_REPORT_LOADING: str = (
    "⏳ در حال دریافت گزارش کامل حجم و کمیسیون..."
)

ADMIN_REPORT: str = (
    "📈 گزارش کامل حجم و کمیسیون\n\n"
    "امروز\n"
    "حجم اسپات: {today_spot} USDT\n"
    "حجم فیوچرز: {today_futures} USDT\n"
    "حجم کل: {today_total} USDT\n"
    "کمیسیون: {today_commission} USDT\n\n"
    "۷ روز گذشته\n"
    "حجم اسپات: {week_spot} USDT\n"
    "حجم فیوچرز: {week_futures} USDT\n"
    "حجم کل: {week_total} USDT\n"
    "کمیسیون: {week_commission} USDT\n\n"
    "از ابتدای ماه\n"
    "حجم اسپات: {month_spot} USDT\n"
    "حجم فیوچرز: {month_futures} USDT\n"
    "حجم کل: {month_total} USDT\n"
    "کمیسیون: {month_commission} USDT"
)
