# Claude Client — Discord-бот, который одной командой !Create собирает готовый сервер:
# роли, категории, текстовые и голосовые каналы, правила, верификацию, выбор ролей, приветствие и логи.
import asyncio
import datetime
import json
import os
import sys

import discord
from discord.ext import commands

for _s in (sys.stdout, sys.stderr):  # эмодзи в консоли Windows
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(HERE, "token.txt")
DATA_FILE = os.path.join(HERE, "data.json")

ORANGE = 0xD97757  # фирменный цвет Claude
LOADSTRING = 'loadstring(game:HttpGet("https://raw.githubusercontent.com/delikiyou-alt/-Claude-Client-/main/Claude_Client.txt"))()'


# ---------- хранилище id каналов и ролей (чтобы кнопки и приветствие работали после перезапуска) ----------
def load_data():
    try:
        with open(DATA_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_data(d):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)


DATA = load_data()


def gdata(guild):
    return DATA.get(str(guild.id), {})


# если data.json потерялся (например, на хостинге после перезапуска) — ищем по имени
FALLBACK_NAMES = {
    "member": "✅ Участник", "p_upd": "🔔 Обновления", "p_news": "📢 Новости", "p_event": "🎉 Ивенты",
    "verify": "✅┃верификация", "welcome": "👋┃приветствие", "logs": "📋┃логи", "ideas": "💡┃идеи",
    "updates": "🔄┃обновления", "news": "📢┃новости", "staff": "🔒┃админ-чат",
}


def g_role(guild, key):
    rid = gdata(guild).get(key)
    return (guild.get_role(rid) if rid else None) or discord.utils.get(guild.roles, name=FALLBACK_NAMES.get(key))


def g_chan(guild, key):
    cid = gdata(guild).get(key)
    return (guild.get_channel(cid) if cid else None) or discord.utils.get(guild.channels, name=FALLBACK_NAMES.get(key))


def embed(title, desc="", color=ORANGE):
    e = discord.Embed(title=title, description=desc, color=color)
    e.set_footer(text="Claude Client")
    return e


# ---------- кнопки (постоянные: работают и после перезапуска бота) ----------
class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Я прочитал правила", emoji="✅", style=discord.ButtonStyle.success, custom_id="cc:verify")
    async def verify(self, inter: discord.Interaction, _):
        role = g_role(inter.guild, "member")
        if not role:
            return await inter.response.send_message("Роль участника не найдена — админ, перезапусти !Create.", ephemeral=True)
        if role in inter.user.roles:
            return await inter.response.send_message("Ты уже участник 👍", ephemeral=True)
        await inter.user.add_roles(role, reason="Верификация")
        await inter.response.send_message("Готово! Тебе открыт весь сервер 🎉", ephemeral=True)


PING_ROLES = [("p_upd", "Обновления", "🔔"), ("p_news", "Новости", "📢"), ("p_event", "Ивенты", "🎉")]


class PingView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        for key, label, emoji in PING_ROLES:
            b = discord.ui.Button(label=label, emoji=emoji, style=discord.ButtonStyle.secondary, custom_id="cc:ping:" + key)
            b.callback = self.make_cb(key, label)
            self.add_item(b)

    @staticmethod
    def make_cb(key, label):
        async def cb(inter: discord.Interaction):
            role = g_role(inter.guild, key)
            if not role:
                return await inter.response.send_message("Роль не найдена.", ephemeral=True)
            if role in inter.user.roles:
                await inter.user.remove_roles(role, reason="Выбор ролей")
                await inter.response.send_message(f"Убрал пинги «{label}» 🔕", ephemeral=True)
            else:
                await inter.user.add_roles(role, reason="Выбор ролей")
                await inter.response.send_message(f"Теперь тебя пингуют: «{label}» 🔔", ephemeral=True)
        return cb


class ConfirmView(discord.ui.View):
    def __init__(self, author):
        super().__init__(timeout=90)
        self.author = author
        self.choice = None

    async def interaction_check(self, inter):
        if inter.user.id != self.author.id:
            await inter.response.send_message("Эти кнопки только для того, кто написал !Create.", ephemeral=True)
            return False
        return True

    async def pick(self, inter, choice):
        self.choice = choice
        for item in self.children:
            item.disabled = True
        await inter.response.edit_message(view=self)
        self.stop()

    @discord.ui.button(label="Снести всё и собрать с нуля", emoji="🧹", style=discord.ButtonStyle.danger)
    async def wipe(self, inter, _):
        await self.pick(inter, "wipe")

    @discord.ui.button(label="Добавить к тому, что есть", emoji="➕", style=discord.ButtonStyle.primary)
    async def add(self, inter, _):
        await self.pick(inter, "add")

    @discord.ui.button(label="Отмена", style=discord.ButtonStyle.secondary)
    async def cancel(self, inter, _):
        await self.pick(inter, None)


# ---------- бот ----------
intents = discord.Intents.default()
intents.members = True
intents.message_content = True


class Bot(commands.Bot):
    async def setup_hook(self):
        self.add_view(VerifyView())
        self.add_view(PingView())


bot = Bot(command_prefix="!", intents=intents, case_insensitive=True, help_command=None)


@bot.event
async def on_ready():
    url = discord.utils.oauth_url(bot.user.id, permissions=discord.Permissions(administrator=True))
    print(f"\n✅ Бот запущен как {bot.user}")
    print(f"🔗 Ссылка, чтобы добавить бота на сервер:\n{url}\n")
    print("Дальше на сервере напиши !Create (окно не закрывай, пока бот нужен).")
    await bot.change_presence(activity=discord.Game("Claude Client · !help"))


# ---------- что строить ----------
RULES = [
    ("Уважение", "Без оскорблений, травли, расизма и токсичности. Спорь по делу, а не с человеком."),
    ("Без 18+ и жести", "Никакого NSFW, шок-контента и гуро — ни в чате, ни на аватарках, ни в никах."),
    ("Без спама и рекламы", "Флуд, капс, спам пингами и реклама других серверов/скриптов — мут."),
    ("Без скама", "Продажа/обмен аккаунтов, «бесплатный Robux», подозрительные ссылки и файлы — бан сразу."),
    ("Личные данные", "Нельзя сливать чужие фото, адреса, номера и переписки."),
    ("По каналам", "Баги — в #баги, идеи — в #идеи, вопросы — в #помощь. Так всё быстрее чинится."),
    ("Не выдавай себя за других", "Нельзя притворяться админом, разработчиком или другим участником."),
    ("Слушай персонал", "Решения модераторов не обсуждаются в общем чате — пиши админу в ЛС."),
    ("Правила Discord", "Действуют Условия использования и Правила сообщества Discord."),
]

FAQ = [
    ("Как запустить?", "Открой свой экзекутор, вставь лоадстринг из #скачать-скрипт и нажми Execute."),
    ("Не грузится / ошибка", "Перезайди в игру и запусти ещё раз. Если не помогло — кинь скрин ошибки в #баги."),
    ("Паук", "F — управлять, WASD — ходить, Shift — бег, Space — прыжок, 1–7 — трюки, X — разобрать."),
    ("Поддоны и лестницы", "В карточке «Поддоны» видно, сколько выбрано. Автосборка сама спавнит и хватает."),
    ("Плот", "В режиме «В плоте» стройся у себя на участке — там твои вещи никто не схватит."),
]

CHANGELOG = (
    "**🎉 Первый релиз Claude Client!**\n\n"
    "🚁 **FPV Lab** — дрон, ИИ-пилот, кольца для пролёта, гигантский FPV из поддонов\n"
    "💥 **Баллистика** — 25 видов ударов\n"
    "🏗️ **Автосборка** — поддоны, ракеты, бенгальские огни и лестницы сами спавнятся и хватаются\n"
    "🕷️ **Пауки из поддонов** — 13 видов (Брутальный, Гигантский, Скорпион, Краб, Многоножка, Тарантул, Титан, Мех, Королева…) и 7 трюков\n"
    "✈️ **Конструкции** — истребитель, трансформер, крылья\n"
    "🏠 **Режим плота** — строй у себя на участке\n"
    "🎨 Новое меню, интро и загрузчик"
)


async def build(ctx, mode, status):
    g = ctx.guild
    me = g.me
    everyone = g.default_role
    ow = discord.PermissionOverwrite
    steps = []

    async def say(line):
        steps.append(line)
        try:
            await status.edit(embed=embed("⏳ Собираю сервер…", "\n".join(steps[-12:])))
        except discord.HTTPException:
            pass

    # 1. снести старое
    if mode == "wipe":
        await say("🧹 Удаляю старые каналы и роли")
        for ch in list(g.channels):
            if ch.id != ctx.channel.id:
                try:
                    await ch.delete(reason="!Create: сборка с нуля")
                except discord.HTTPException:
                    pass
        for r in list(g.roles):
            if not r.is_default() and not r.managed and r < me.top_role:
                try:
                    await r.delete(reason="!Create: сборка с нуля")
                except discord.HTTPException:
                    pass

    # 2. роли (создаются сверху вниз: каждая новая встаёт под предыдущую)
    await say("🎭 Создаю роли")
    P = discord.Permissions
    role_specs = [
        ("owner", "👑 Создатель", 0xF1C40F, P(administrator=True), True, False),
        ("admin", "🛡️ Админ", 0xE74C3C, P(administrator=True), True, False),
        ("mod", "🔨 Модератор", 0xE67E22, P(kick_members=True, ban_members=True, manage_messages=True, moderate_members=True,
                                          mute_members=True, deafen_members=True, move_members=True, manage_nicknames=True,
                                          view_audit_log=True, manage_threads=True), True, False),
        ("bot", "🤖 Бот", 0x5865F2, P.none(), True, False),
        ("tester", "🧪 Тестер", 0x9B59B6, P.none(), True, False),
        ("creator", "🎬 Контент-мейкер", 0xFF5DA2, P.none(), True, False),
        ("sponsor", "💎 Спонсор", 0x1ABC9C, P.none(), True, False),
        ("member", "✅ Участник", 0x2ECC71, P.none(), False, False),
        ("p_upd", "🔔 Обновления", 0x95A5A6, P.none(), False, True),
        ("p_news", "📢 Новости", 0x95A5A6, P.none(), False, True),
        ("p_event", "🎉 Ивенты", 0x95A5A6, P.none(), False, True),
    ]
    R = {}
    for key, name, color, perms, hoist, mention in role_specs:
        R[key] = await g.create_role(name=name, colour=discord.Colour(color), permissions=perms, hoist=hoist,
                                     mentionable=mention, reason="!Create")
    try:
        owner = g.owner or await g.fetch_member(g.owner_id)
        await owner.add_roles(R["owner"], reason="!Create")
        await me.add_roles(R["bot"], reason="!Create")
    except discord.HTTPException:
        pass

    # что могут все по умолчанию (а видимость решают каналы)
    await everyone.edit(permissions=P(view_channel=True, send_messages=True, read_message_history=True, add_reactions=True,
                                      embed_links=True, attach_files=True, use_external_emojis=True, use_external_stickers=True,
                                      connect=True, speak=True, stream=True, use_voice_activation=True, change_nickname=True,
                                      create_instant_invite=True, send_messages_in_threads=True, create_public_threads=True,
                                      use_application_commands=True), reason="!Create")

    # 3. права для типов каналов
    info = {everyone: ow(view_channel=True, send_messages=False, add_reactions=True, create_public_threads=False),
            R["mod"]: ow(send_messages=True)}
    members = {everyone: ow(view_channel=False), R["member"]: ow(view_channel=True), R["mod"]: ow(view_channel=True)}
    readonly = {**members, R["member"]: ow(view_channel=True, send_messages=False, add_reactions=True), R["mod"]: ow(view_channel=True, send_messages=True)}
    staff = {everyone: ow(view_channel=False), R["mod"]: ow(view_channel=True)}
    testers = {everyone: ow(view_channel=False), R["tester"]: ow(view_channel=True), R["mod"]: ow(view_channel=True)}
    verify_ow = {everyone: ow(view_channel=True, send_messages=False, add_reactions=False), R["member"]: ow(view_channel=False)}

    C = {}

    async def cat(name, perms):
        await say("📁 " + name)
        return await g.create_category(name, overwrites=perms, reason="!Create")

    async def text(key, name, category, perms, topic="", slow=0):
        C[key] = await g.create_text_channel(name, category=category, overwrites=perms, topic=topic, slowmode_delay=slow, reason="!Create")
        return C[key]

    async def voice(key, name, category, perms, limit=0):
        C[key] = await g.create_voice_channel(name, category=category, overwrites=perms, user_limit=limit, reason="!Create")
        return C[key]

    # 4. каналы
    c = await cat("📌 ИНФОРМАЦИЯ", info)
    await text("verify", "✅┃верификация", c, verify_ow, "Нажми кнопку, чтобы открыть сервер")
    await text("rules", "📜┃правила", c, info, "Правила сервера")
    await text("news", "📢┃новости", c, info, "Новости Claude Client")
    await text("updates", "🔄┃обновления", c, info, "Чейнджлог: что нового в каждой версии")
    await text("download", "📥┃скачать-скрипт", c, info, "Лоадстринг Claude Client")
    await text("roles", "🔔┃выбор-ролей", c, info, "Выбери, о чём тебя пинговать")
    await text("welcome", "👋┃приветствие", c, info, "Новые участники")

    c = await cat("💬 ОБЩЕНИЕ", members)
    await text("general", "💬┃общий", c, members, "Болталка обо всём", slow=2)
    await text("media", "🖼️┃медиа", c, members, "Скрины и видео")
    await text("memes", "😂┃мемы", c, members, "Мемы")
    await text("cmds", "🤖┃команды", c, members, "Команды ботов")

    c = await cat("🕷️ CLAUDE CLIENT", members)
    await text("help", "❓┃помощь", c, members, "Вопросы по скрипту", slow=5)
    await text("bugs", "🐛┃баги", c, members, "Нашёл баг — опиши по шаблону", slow=10)
    await text("ideas", "💡┃идеи", c, members, "Идеи для новых функций — голосуй 👍/👎", slow=30)
    await text("clips", "🎥┃клипы", c, members, "Твои видео с Claude Client")
    await text("builds", "🏗️┃постройки", c, members, "Пауки, джеты и всё, что ты собрал")
    await text("faq", "📖┃faq", c, readonly, "Частые вопросы")
    await text("testers", "🧪┃тестеры", c, testers, "Тест новых версий до релиза")

    c = await cat("🔊 ГОЛОСОВЫЕ", members)
    await voice("v_general", "🔊 Общий", c, members)
    await voice("v_ftap1", "🎮 FTAP #1", c, members)
    await voice("v_ftap2", "🎮 FTAP #2", c, members)
    await voice("v_music", "🎵 Музыка", c, members)
    await voice("v_stream", "🎙️ Стрим", c, members)
    await voice("v_duo", "👥 Дуо", c, members, limit=2)
    await voice("v_trio", "👥 Трио", c, members, limit=3)
    await voice("afk", "💤 AFK", c, {**members, R["member"]: ow(view_channel=True, speak=False)})

    c = await cat("🛡️ ПЕРСОНАЛ", staff)
    await text("staff", "🔒┃админ-чат", c, staff, "Только для персонала")
    await text("logs", "📋┃логи", c, staff, "Удалённые/изменённые сообщения, входы и выходы")
    await voice("v_staff", "🔒 Совещание", c, staff)

    # 5. настройки сервера
    await say("⚙️ Настраиваю сервер")
    try:
        await g.edit(afk_channel=C["afk"], afk_timeout=300, system_channel=None,
                     verification_level=discord.VerificationLevel.low,
                     default_notifications=discord.NotificationLevel.only_mentions,
                     explicit_content_filter=discord.ContentFilter.all_members, reason="!Create")
    except discord.HTTPException:
        pass

    DATA[str(g.id)] = {k: v.id for k, v in R.items()} | {k: v.id for k, v in C.items()}
    save_data(DATA)

    # 6. наполнение
    await say("✍️ Пишу правила, FAQ и чейнджлог")
    e = embed("✅ Добро пожаловать на сервер Claude Client!",
              f"Прочитай {C['rules'].mention} и нажми кнопку ниже — откроются все каналы.")
    await C["verify"].send(embed=e, view=VerifyView())

    e = embed("📜 Правила сервера", "Нарушение — предупреждение, мут или бан (на усмотрение персонала).")
    for i, (t, d) in enumerate(RULES, 1):
        e.add_field(name=f"{i}. {t}", value=d, inline=False)
    await C["rules"].send(embed=e)

    e = embed("📥 Скачать Claude Client", "Вставь это в свой экзекутор и нажми **Execute**:\n```lua\n" + LOADSTRING + "\n```")
    e.add_field(name="Обновления", value=f"Скрипт всегда свежий — ссылка не меняется. Что нового — в {C['updates'].mention}.", inline=False)
    await C["download"].send(embed=e)

    e = embed("🔄 Claude Client v1.0", CHANGELOG)
    e.timestamp = discord.utils.utcnow()
    await C["updates"].send(embed=e)

    await C["news"].send(embed=embed("🚀 Сервер открыт!", f"Здесь будут новости Claude Client. Хочешь пинги — выбери роли в {C['roles'].mention}."))

    await C["roles"].send(embed=embed("🔔 Выбор ролей", "Нажми на кнопку, чтобы получать пинги. Нажми ещё раз — чтобы убрать.\n\n"
                                       "🔔 **Обновления** — вышла новая версия\n📢 **Новости** — важные объявления\n🎉 **Ивенты** — конкурсы и розыгрыши"),
                          view=PingView())

    e = embed("📖 Частые вопросы")
    for t, d in FAQ:
        e.add_field(name=t, value=d, inline=False)
    await C["faq"].send(embed=e)

    await C["bugs"].send(embed=embed("🐛 Как сообщить о баге", "Скопируй и заполни:\n```\nЧто сломалось:\nЧто делал перед этим:\nЭкзекутор:\nСкрин/видео: (прикрепи)\n```"))
    await C["ideas"].send(embed=embed("💡 Идеи", "Одна идея — одно сообщение. Бот сам поставит 👍 и 👎, лучшие попадут в обновления."))
    await C["help"].send(embed=embed("❓ Помощь", f"Сначала загляни в {C['faq'].mention}. Не нашёл ответ — спрашивай тут."))

    e = embed("🛡️ Админ-панель", "Сервер собран. Команды бота:")
    e.add_field(name="!post <текст>", value=f"Пост в {C['updates'].mention} с пингом 🔔 Обновления", inline=False)
    e.add_field(name="!news <текст>", value=f"Пост в {C['news'].mention} с пингом 📢 Новости", inline=False)
    e.add_field(name="!mute @ник <минуты> [причина]", value="Тайм-аут (по умолчанию 10 минут)", inline=False)
    e.add_field(name="!unmute @ник", value="Снять тайм-аут", inline=False)
    e.add_field(name="!clear <число>", value="Удалить последние сообщения (до 100)", inline=False)
    e.add_field(name="Роли персонала", value=f"Выдавай {R['admin'].mention}, {R['mod'].mention}, {R['tester'].mention} через настройки сервера.", inline=False)
    await C["staff"].send(embed=e)
    return C


@bot.command(name="create")
@commands.guild_only()
async def create(ctx):
    if not (ctx.author.id == ctx.guild.owner_id or ctx.author.guild_permissions.administrator):
        return await ctx.send("❌ Собирать сервер может только владелец или админ.")
    if not ctx.guild.me.guild_permissions.administrator:
        return await ctx.send("❌ Дай боту право **Администратор**: добавь его заново по ссылке из окна бота (галочка Administrator).")
    view = ConfirmView(ctx.author)
    msg = await ctx.send(embed=embed("🏗️ Собрать сервер Claude Client?",
                                     "Будет: 11 ролей, 5 категорий, 20 текстовых и 9 голосовых каналов, правила, верификация, "
                                     "выбор ролей, FAQ, чейнджлог, приветствие и логи.\n\n"
                                     "🧹 **Снести всё** — удалит ВСЕ старые каналы и роли (для пустого сервера).\n"
                                     "➕ **Добавить** — старое оставит, новое создаст рядом."), view=view)
    await view.wait()
    if not view.choice:
        return await msg.edit(embed=embed("Отменено", ""), view=None)
    status = await ctx.send(embed=embed("⏳ Собираю сервер…", "Это займёт около минуты."))
    try:
        C = await build(ctx, view.choice, status)
    except discord.Forbidden:
        return await ctx.send("❌ Не хватает прав. Перетащи роль бота выше всех остальных в Настройки сервера → Роли.")
    done = embed("✅ Сервер готов!", f"Начни с {C['verify'].mention}. Команды для персонала — в {C['staff'].mention}.", 0x2ECC71)
    if view.choice == "wipe":
        await C["staff"].send(embed=done)
        await status.edit(embed=embed("✅ Готово", "Этот канал удалится через 10 секунд — сервер уже собран.", 0x2ECC71))
        await asyncio.sleep(10)
        try:
            await ctx.channel.delete(reason="!Create: старый канал")
        except discord.HTTPException:
            pass
    else:
        await status.edit(embed=done)


async def announce(ctx, key_chan, key_role, title, text):
    ch, role = g_chan(ctx.guild, key_chan), g_role(ctx.guild, key_role)
    if not ch:
        return await ctx.send("❌ Сначала собери сервер: !Create")
    e = embed(title, text)
    e.timestamp = discord.utils.utcnow()
    e.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)
    await ch.send(content=role.mention if role else None, embed=e,
                  allowed_mentions=discord.AllowedMentions(roles=True))
    await ctx.message.add_reaction("✅")


@bot.command(name="post")
@commands.has_permissions(administrator=True)
async def post(ctx, *, text):
    await announce(ctx, "updates", "p_upd", "🔄 Обновление Claude Client", text)


@bot.command(name="news")
@commands.has_permissions(administrator=True)
async def news(ctx, *, text):
    await announce(ctx, "news", "p_news", "📢 Новости", text)


@bot.command(name="mute")
@commands.has_permissions(moderate_members=True)
async def mute(ctx, member: discord.Member, minutes: int = 10, *, reason: str = "без причины"):
    await member.timeout(datetime.timedelta(minutes=max(1, min(minutes, 40320))), reason=reason)
    await ctx.send(f"🔇 {member.mention} в муте на {minutes} мин. Причина: {reason}")


@bot.command(name="unmute")
@commands.has_permissions(moderate_members=True)
async def unmute(ctx, member: discord.Member):
    await member.timeout(None)
    await ctx.send(f"🔊 {member.mention} снова может писать.")


@bot.command(name="clear")
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int = 10):
    deleted = await ctx.channel.purge(limit=max(1, min(amount, 100)) + 1)
    await ctx.send(f"🧹 Удалено {len(deleted) - 1} сообщений.", delete_after=4)


@bot.command(name="help", aliases=["помощь", "команды"])
async def help_cmd(ctx):
    e = embed("🤖 Команды бота Claude Client")
    e.add_field(name="!create", value="Собрать сервер (владелец/админ)", inline=False)
    e.add_field(name="!post / !news <текст>", value="Объявление с пингом (админ)", inline=False)
    e.add_field(name="!mute / !unmute / !clear", value="Модерация", inline=False)
    await ctx.send(embed=e)


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, (commands.MissingPermissions, commands.NoPrivateMessage)):
        return await ctx.send("❌ У тебя нет прав на эту команду.")
    if isinstance(error, (commands.MissingRequiredArgument, commands.BadArgument)):
        return await ctx.send("❌ Неправильно написана команда — смотри !help")
    print("Ошибка команды:", repr(error), file=sys.stderr)
    await ctx.send(f"⚠️ Ошибка: {error}")


# ---------- приветствие, идеи, логи ----------
@bot.event
async def on_member_join(member):
    ch = g_chan(member.guild, "welcome")
    if ch:
        verify = g_chan(member.guild, "verify")
        e = embed("👋 Новый участник!", f"Привет, {member.mention}! Ты **{member.guild.member_count}-й** на сервере.\n"
                                        f"Открой сервер в {verify.mention if verify else '#верификация'} и забирай скрипт 🕷️")
        e.set_thumbnail(url=member.display_avatar.url)
        await ch.send(embed=e)
    await log(member.guild, "📥 Зашёл", f"{member.mention} (`{member}`), аккаунт создан {discord.utils.format_dt(member.created_at, 'R')}", 0x2ECC71)


@bot.event
async def on_member_remove(member):
    await log(member.guild, "📤 Вышел", f"`{member}`", 0x95A5A6)


@bot.event
async def on_message(msg):
    if msg.author.bot or not msg.guild:
        return
    ideas = g_chan(msg.guild, "ideas")
    if ideas and msg.channel.id == ideas.id:
        for r in ("👍", "👎"):
            await msg.add_reaction(r)
    await bot.process_commands(msg)


async def log(guild, title, text, color=ORANGE):
    ch = g_chan(guild, "logs")
    if ch:
        e = embed(title, text[:4000], color)
        e.timestamp = discord.utils.utcnow()
        try:
            await ch.send(embed=e)
        except discord.HTTPException:
            pass


@bot.event
async def on_message_delete(msg):
    if msg.guild and not msg.author.bot:
        await log(msg.guild, "🗑️ Сообщение удалено", f"{msg.author.mention} в {msg.channel.mention}:\n{msg.content or '(без текста)'}", 0xE74C3C)


@bot.event
async def on_message_edit(before, after):
    if before.guild and not before.author.bot and before.content != after.content:
        await log(before.guild, "✏️ Сообщение изменено",
                  f"{before.author.mention} в {before.channel.mention} ([перейти]({after.jump_url}))\n**Было:** {before.content[:1500]}\n**Стало:** {after.content[:1500]}")


# ---------- запуск ----------
def read_token():
    env = os.environ.get("DISCORD_TOKEN", "").strip()  # на хостинге (Railway) токен лежит в переменной
    if env:
        return env
    try:
        with open(TOKEN_FILE, encoding="utf-8-sig") as f:
            t = f.read().strip()
    except OSError:
        t = ""
    return t if len(t) > 50 and " " not in t else None


if __name__ == "__main__":
    token = read_token()
    if not token:
        print("❌ Нет токена. Открой token.txt, вставь туда токен бота (из Discord Developer Portal → Bot → Reset Token) и сохрани.")
        print("Подробно — в ИНСТРУКЦИЯ.txt")
        sys.exit(1)
    try:
        bot.run(token)
    except discord.LoginFailure:
        print("❌ Токен неправильный. Сделай Reset Token в Developer Portal и вставь новый в token.txt")
    except discord.PrivilegedIntentsRequired:
        print("❌ Включи в Developer Portal → Bot: SERVER MEMBERS INTENT и MESSAGE CONTENT INTENT, нажми Save и запусти снова.")
