"""Interface strings for the exam site, in English and Ukrainian.

Exam content (questions, options, explanations) comes from the JSON files in
jsons/. These are only the words around it. Placeholders use str.format names;
`{brand}` is filled in by the template layer, and `{<word>_word}` placeholders
are filled with the right plural form for `n` (see PLURALS).
"""

from datetime import datetime

DEFAULT_LANG = "en"

PLURALS: dict[str, dict[str, tuple[str, ...]]] = {
    "questions": {"en": ("question", "questions"), "uk": ("питання", "питання", "питань")},
    "attempts": {"en": ("attempt", "attempts"), "uk": ("спроба", "спроби", "спроб")},
}

_UK_MONTHS = (
    "січня", "лютого", "березня", "квітня", "травня", "червня",
    "липня", "серпня", "вересня", "жовтня", "листопада", "грудня",
)

UI: dict[str, dict[str, str]] = {
    "en": {
        # ── Site chrome ──
        "lang_name": "English",
        "lang_switch_label": "Language",
        "tagline": "ICF ACC practice exams",
        "meta_description": "Timed, scenario-based practice exams for the ICF ACC credential, with a score for each competency and an explanation for every answer. In English and Ukrainian.",
        "skip_link": "Skip to content",
        "nav_home": "Home",
        "nav_signin": "Sign in",
        "nav_account": "Account",
        "footer_disclaimer": "{brand} is an independent practice tool. It is not affiliated with, endorsed by or sponsored by the International Coaching Federation (ICF). ICF, ACC and related marks belong to the International Coaching Federation.",
        "footer_privacy": "Privacy",
        "footer_terms": "Terms",

        # ── Exam list ──
        "exams_title": "ACC practice exams",
        "exams_intro": "Unofficial practice for the ICF ACC exam, not affiliated with ICF. Each set has 60 questions in two 39-minute sections with a 10-minute break, like the real exam. Pass mark here: 70%.",
        "guest_intro": "No account needed. Sign in only if you want your results on other devices.",
        "empty": "There are no exams in this language yet.",
        "empty_hint": "Switch languages at the top of the page to see the other exams.",
        "card_meta": "{n} {questions_word}, 2 timed sections",
        "status_new": "Not started",
        "status_progress": "In progress",
        "status_best": "Best score {pct}%",
        "status_attempts": "{n} {attempts_word}",
        "start": "Start exam",
        "resume": "Resume exam",
        "practice_btn": "Practice",
        "progress_title": "Your progress",
        "progress_sub": "Your score on each finished exam, oldest first. The dashed line is the 70% pass mark.",
        "progress_chart_label": "Scores on your last {n} exams",
        "history_title": "Recent results",
        "history_date": "Date",
        "history_exam": "Exam",
        "history_score": "Score",
        "history_view": "View",

        # ── Exam ──
        "section_of": "Section {n} of 2",
        "question_of": "Question {i} of {total}",
        "item_of": "{i} of {total}",
        "time_remaining": "Time Remaining",
        "flag": "Flag for Review",
        "prev": "Previous",
        "next": "Next",
        "review_screen": "Review Screen",
        "review_screen_title": "Item Review Screen",
        "review_instructions": "Instructions",
        "review_intro": "Below is a summary of your answers. You can review your questions in three ways, with the buttons in the lower right-hand corner:",
        "review_way_all": "Review all of your questions and answers.",
        "review_way_incomplete": "Review questions that are incomplete.",
        "review_way_flagged": "Review questions that are flagged for review. (Click the flag icon to change the flag status.)",
        "review_jump": "You can also click a question number to go straight to it.",
        "review_lock": "Once you select End Review, you leave this section and can't go back to it.",
        "keys_hint": "Keyboard: A–D to answer, ← and → to move, F to flag.",
        "review_incomplete_count": "{n} unseen/incomplete",
        "incomplete": "Incomplete",
        "review_all": "Review All",
        "review_incomplete": "Review Incomplete",
        "review_flagged": "Review Flagged",
        "end_review": "End Review",
        "end_review_title": "End review",
        "end_review_s1": "If you select Yes, section 1 ends. You can't return to it or change its answers. A 10-minute break comes next.",
        "end_review_s2": "If you select Yes, the exam ends and is scored. Unanswered questions count as incorrect.",
        "yes": "Yes",
        "no": "No",
        "restored": "Welcome back. Your answers and remaining time were restored.",
        "break": "Break",
        "break_title": "Scheduled break",
        "break_text": "Section 1 is closed. Section 2 starts automatically when the break ends.",
        "break_timeup": "Time ran out for section 1, so it was closed automatically.",
        "break_start": "End break and start section 2",
        "submitting": "Scoring your exam…",

        # ── Practice ──
        "practice_title": "Practice: {title}",
        "practice_sub": "No timer. Check each answer to see the correct one and the explanation.",
        "practice_area": "Showing only questions on {area}.",
        "practice_show_all": "Show all questions",
        "practice_score": "{c} of {n} correct so far",
        "practice_done": "That was the last question.",
        "practice_restart": "Start again",
        "practice_timed": "Take the timed exam",
        "check": "Check answer",
        "answer_correct": "Correct.",
        "answer_wrong": "Not quite. The best answer is {id}.",
        "check_failed": "We couldn't check your answer. Check your connection and try again.",
        "back_to_exams": "All exams",

        # ── Results ──
        "results_title": "Results",
        "passed_title": "You passed",
        "passed_text": "{score} of {total} correct. The pass mark is {p}.",
        "failed_title": "Not yet",
        "failed_text": "{score} of {total} correct. You need {p} to pass: {k} more correct answers.",
        "q_correct": "Correct",
        "q_wrong": "Wrong",
        "q_unanswered": "Unanswered",
        "time_taken": "Time taken",
        "minutes_short": "{m} min",
        "areas_title": "Score by area",
        "areas_sub": "Weakest areas first. The mark on each bar is the 70% pass line.",
        "area_ethics": "Code of Ethics",
        "area_practice": "Practice",
        "next_practice_weak": "Practice your weakest area",
        "next_practice_all": "Practice this exam with explanations",
        "next_retake": "Retake this exam",
        "next_other": "Try {title}",
        "save_text": "This result is saved in this browser. Create an account to keep it on any device.",
        "breakdown": "Review your answers",
        "filter_label": "Show",
        "filter_all": "All ({n})",
        "filter_wrong": "Wrong ({n})",
        "filter_unanswered": "Unanswered ({n})",
        "filter_correct": "Correct ({n})",
        "filter_empty": "No questions in this group.",
        "q_label": "Question {n}",
        "marker_correct": "Correct answer",
        "marker_yours": "Your answer",
        "explanation": "Explanation",

        # ── Sign in ──
        "login_title": "Sign in",
        "register_title": "Create an account",
        "register_text": "Optional. An account keeps your results on any device.",
        "username_label": "Username",
        "username_hint": "3–32 characters: letters, numbers, dots, dashes or underscores.",
        "password_label": "Password",
        "password_hint": "At least 8 characters.",
        "register_note": "There's no password reset, so keep your password somewhere safe.",
        "password2_label": "Repeat password",
        "login_btn": "Sign in",
        "register_btn": "Create account",
        "login_wrong": "That username and password don't match. Check both and try again.",
        "username_invalid": "Use 3–32 characters: letters, numbers, dots, dashes or underscores.",
        "username_taken": "That username is taken. Try another one.",
        "password_short": "Use at least 8 characters.",
        "password_mismatch": "The passwords don't match.",
        "account_user": "Signed in as {username}",
        "save_create": "Create an account",
        "save_signin": "Sign in",
        "signed_in": "You're signed in as {username}.",
        "results_claimed": "Results from this device were added to your account.",

        # ── Account ──
        "account_title": "Account",
        "sign_out": "Sign out",
        "signed_out": "You're signed out.",
        "delete_title": "Delete account",
        "delete_text": "This permanently deletes your account and all of your saved results.",
        "delete_confirm_label": "I understand that this can't be undone",
        "delete_btn": "Delete my account",
        "deleted": "Your account and results were deleted.",
        "csrf_failed": "That form expired. Try again.",
        "not_found_title": "Page not found",
        "not_found_text": "The link may be old or mistyped.",

        # ── Legal ──
        "privacy_title": "Privacy",
        "terms_title": "Terms of use",
        "legal_updated": "Last updated {date}",

        # ── Answer key (owner only) ──
        "admin_login_title": "Answer key",
        "admin_login_text": "Enter the admin password to see every question with its correct answer.",
        "admin_password": "Password",
        "admin_wrong": "That password isn't right.",
        "admin_signin": "Open answer key",
        "admin_signout": "Close answer key",
        "admin_picker_title": "Answer key",
        "admin_picker_sub": "Every exam, in every language, with correct answers and explanations. Only you can see this page.",
        "admin_prefix": "Answer key",
        "all_tests": "All exams",
        "browse": "View answers",
        "n_questions": "{n} {questions_word}",
    },
    "uk": {
        # ── Site chrome ──
        "lang_name": "Українська",
        "lang_switch_label": "Мова",
        "tagline": "Пробні іспити ICF ACC",
        "meta_description": "Пробні іспити з таймером для кредитації ICF ACC: ситуаційні питання, бал за кожною компетенцією та пояснення до кожної відповіді. Українською та англійською.",
        "skip_link": "Перейти до змісту",
        "nav_home": "Головна",
        "nav_signin": "Увійти",
        "nav_account": "Акаунт",
        "footer_disclaimer": "{brand} — незалежний інструмент для підготовки. Він не пов’язаний із Міжнародною федерацією коучингу (ICF), не схвалений і не спонсорований нею. ICF, ACC та пов’язані позначення належать Міжнародній федерації коучингу.",
        "footer_privacy": "Конфіденційність",
        "footer_terms": "Умови",

        # ── Exam list ──
        "exams_title": "Пробні іспити ACC",
        "exams_intro": "Неофіційна підготовка до іспиту ICF ACC, не пов’язана з ICF. Кожен варіант має 60 питань у двох частинах по 39 хвилин із 10-хвилинною перервою, як на справжньому іспиті. Прохідний бал тут — 70%.",
        "guest_intro": "Акаунт не потрібен. Увійдіть, лише якщо хочете бачити результати на інших пристроях.",
        "empty": "Іспитів цією мовою поки немає.",
        "empty_hint": "Змініть мову вгорі сторінки, щоб побачити інші іспити.",
        "card_meta": "{n} {questions_word}, 2 частини з таймером",
        "status_new": "Ще не проходили",
        "status_progress": "Розпочато",
        "status_best": "Найкращий результат: {pct}%",
        "status_attempts": "{n} {attempts_word}",
        "start": "Почати іспит",
        "resume": "Продовжити іспит",
        "practice_btn": "Тренування",
        "progress_title": "Ваш прогрес",
        "progress_sub": "Результат кожного завершеного іспиту, від найстаршого. Пунктирна лінія — прохідний бал 70%.",
        "progress_chart_label": "Результати останніх іспитів: {n}",
        "history_title": "Останні результати",
        "history_date": "Дата",
        "history_exam": "Іспит",
        "history_score": "Бал",
        "history_view": "Переглянути",

        # ── Exam ──
        "section_of": "Частина {n} з 2",
        "question_of": "Питання {i} з {total}",
        "item_of": "{i} з {total}",
        "time_remaining": "Залишилось часу",
        "flag": "Позначити для перегляду",
        "prev": "Попереднє",
        "next": "Наступне",
        "review_screen": "Екран перегляду",
        "review_screen_title": "Екран перегляду питань",
        "review_instructions": "Інструкції",
        "review_intro": "Нижче — підсумок ваших відповідей. Переглянути питання можна трьома способами за допомогою кнопок у правому нижньому куті:",
        "review_way_all": "Переглянути всі питання й відповіді.",
        "review_way_incomplete": "Переглянути питання без відповіді.",
        "review_way_flagged": "Переглянути питання, позначені для перегляду. (Натисніть на прапорець, щоб змінити позначку.)",
        "review_jump": "Також можна натиснути номер питання, щоб перейти просто до нього.",
        "review_lock": "Після натискання «Завершити перегляд» ви вийдете з цієї частини й не зможете до неї повернутися.",
        "keys_hint": "Клавіші: A–D — відповідь, ← і → — перехід, F — позначка.",
        "review_incomplete_count": "без відповіді: {n}",
        "incomplete": "Без відповіді",
        "review_all": "Переглянути всі",
        "review_incomplete": "Переглянути без відповіді",
        "review_flagged": "Переглянути позначені",
        "end_review": "Завершити перегляд",
        "end_review_title": "Завершення перегляду",
        "end_review_s1": "Якщо натиснете «Так», частину 1 буде завершено. Повернутися до неї чи змінити відповіді вже не вийде. Далі — 10-хвилинна перерва.",
        "end_review_s2": "Якщо натиснете «Так», іспит буде завершено й оцінено. Питання без відповіді зараховуються як неправильні.",
        "yes": "Так",
        "no": "Ні",
        "restored": "З поверненням! Ваші відповіді та залишок часу відновлено.",
        "break": "Перерва",
        "break_title": "Запланована перерва",
        "break_text": "Частину 1 закрито. Частина 2 почнеться автоматично, коли закінчиться перерва.",
        "break_timeup": "Час на частину 1 вичерпано, тому її закрито автоматично.",
        "break_start": "Завершити перерву й почати частину 2",
        "submitting": "Підраховуємо результат…",

        # ── Practice ──
        "practice_title": "Тренування: {title}",
        "practice_sub": "Без таймера. Перевіряйте кожну відповідь, щоб побачити правильну та пояснення.",
        "practice_area": "Показано лише питання з теми «{area}».",
        "practice_show_all": "Показати всі питання",
        "practice_score": "Правильно: {c} з {n}",
        "practice_done": "Це було останнє питання.",
        "practice_restart": "Почати спочатку",
        "practice_timed": "Пройти іспит із таймером",
        "check": "Перевірити відповідь",
        "answer_correct": "Правильно.",
        "answer_wrong": "Не зовсім. Найкраща відповідь — {id}.",
        "check_failed": "Не вдалося перевірити відповідь. Перевірте з’єднання та спробуйте ще раз.",
        "back_to_exams": "Усі іспити",

        # ── Results ──
        "results_title": "Результати",
        "passed_title": "Іспит складено",
        "passed_text": "Правильних відповідей: {score} з {total}. Прохідний бал — {p}.",
        "failed_title": "Поки що не складено",
        "failed_text": "Правильних відповідей: {score} з {total}. Щоб скласти, потрібно {p} — бракує ще {k}.",
        "q_correct": "Правильно",
        "q_wrong": "Неправильно",
        "q_unanswered": "Без відповіді",
        "time_taken": "Витрачений час",
        "minutes_short": "{m} хв",
        "areas_title": "Бал за темами",
        "areas_sub": "Найслабші теми — вгорі. Позначка на кожній смузі — прохідний рівень 70%.",
        "area_ethics": "Етичний кодекс ICF",
        "area_practice": "Тренувати",
        "next_practice_weak": "Потренувати найслабшу тему",
        "next_practice_all": "Пройти цей іспит у режимі тренування",
        "next_retake": "Пройти цей іспит ще раз",
        "next_other": "Спробувати «{title}»",
        "save_text": "Цей результат збережено в цьому браузері. Створіть акаунт, щоб бачити його на будь-якому пристрої.",
        "breakdown": "Перегляд відповідей",
        "filter_label": "Показати",
        "filter_all": "Усі ({n})",
        "filter_wrong": "Неправильні ({n})",
        "filter_unanswered": "Без відповіді ({n})",
        "filter_correct": "Правильні ({n})",
        "filter_empty": "У цій групі немає питань.",
        "q_label": "Питання {n}",
        "marker_correct": "Правильна відповідь",
        "marker_yours": "Ваша відповідь",
        "explanation": "Пояснення",

        # ── Sign in ──
        "login_title": "Вхід",
        "register_title": "Створіть акаунт",
        "register_text": "Необов’язково. Акаунт зберігає ваші результати на будь-якому пристрої.",
        "username_label": "Ім’я користувача",
        "username_hint": "3–32 символи: літери, цифри, крапки, дефіси або підкреслення.",
        "password_label": "Пароль",
        "password_hint": "Щонайменше 8 символів.",
        "register_note": "Відновити пароль не можна, тож збережіть його в надійному місці.",
        "password2_label": "Повторіть пароль",
        "login_btn": "Увійти",
        "register_btn": "Створити акаунт",
        "login_wrong": "Ім’я користувача або пароль неправильні. Перевірте й спробуйте ще раз.",
        "username_invalid": "Використайте 3–32 символи: літери, цифри, крапки, дефіси або підкреслення.",
        "username_taken": "Це ім’я вже зайняте. Спробуйте інше.",
        "password_short": "Використайте щонайменше 8 символів.",
        "password_mismatch": "Паролі не збігаються.",
        "account_user": "Ви увійшли як {username}",
        "save_create": "Створити акаунт",
        "save_signin": "Увійти",
        "signed_in": "Ви увійшли як {username}.",
        "results_claimed": "Результати з цього пристрою додано до вашого акаунта.",

        # ── Account ──
        "account_title": "Акаунт",
        "sign_out": "Вийти",
        "signed_out": "Ви вийшли з акаунта.",
        "delete_title": "Видалити акаунт",
        "delete_text": "Це остаточно видалить ваш акаунт і всі збережені результати.",
        "delete_confirm_label": "Я розумію, що цю дію не можна скасувати",
        "delete_btn": "Видалити мій акаунт",
        "deleted": "Ваш акаунт і результати видалено.",
        "csrf_failed": "Термін дії форми минув. Спробуйте ще раз.",
        "not_found_title": "Сторінку не знайдено",
        "not_found_text": "Можливо, посилання застаріло або містить помилку.",

        # ── Legal ──
        "privacy_title": "Конфіденційність",
        "terms_title": "Умови використання",
        "legal_updated": "Оновлено {date}",

        # ── Answer key (owner only) ──
        "admin_login_title": "Ключі відповідей",
        "admin_login_text": "Введіть пароль адміністратора, щоб побачити всі питання з правильними відповідями.",
        "admin_password": "Пароль",
        "admin_wrong": "Пароль неправильний.",
        "admin_signin": "Відкрити ключі відповідей",
        "admin_signout": "Закрити ключі відповідей",
        "admin_picker_title": "Ключі відповідей",
        "admin_picker_sub": "Усі іспити всіма мовами з правильними відповідями та поясненнями. Цю сторінку бачите лише ви.",
        "admin_prefix": "Ключі відповідей",
        "all_tests": "Усі іспити",
        "browse": "Переглянути відповіді",
        "n_questions": "{n} {questions_word}",
    },
}

# Strings the exam and practice pages' JavaScript needs.
EXAM_JS_KEYS = (
    "section_of", "item_of", "break", "q_label", "flag", "incomplete",
    "review_incomplete_count", "end_review_s1", "end_review_s2",
)
PRACTICE_JS_KEYS = (
    "answer_correct", "answer_wrong", "check_failed", "practice_score",
    "question_of", "marker_correct", "marker_yours", "explanation",
)


def plural(word: str, n: int, lang: str) -> str:
    forms = PLURALS[word][lang if lang in PLURALS[word] else DEFAULT_LANG]
    if len(forms) == 3:
        if n % 10 == 1 and n % 100 != 11:
            return forms[0]
        if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
            return forms[1]
        return forms[2]
    return forms[0] if n == 1 else forms[1]


def questions_word(n: int, lang: str) -> str:
    return plural("questions", n, lang)


def fmt(lang: str, key: str, **kwargs) -> str:
    template = UI[lang][key]
    if "n" in kwargs:
        for word in PLURALS:
            kwargs.setdefault(f"{word}_word", plural(word, kwargs["n"], lang))
    return template.format(**kwargs)


def format_date(value: datetime, lang: str) -> str:
    if lang == "uk":
        return f"{value.day} {_UK_MONTHS[value.month - 1]} {value.year}"
    return value.strftime("%b %-d, %Y")
