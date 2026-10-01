"""
بوت اللفل + الترحيب + لوحة التحكم
-----------------------------------
الميزات:
- نظام XP ولفل تلقائي (مع قدرة الأدمن على تحديد أي لفل يبيه لأي عضو)
- أمر /رتبتي و /المتصدرين
- أمر /افتار : بطاقة صورة (خلفية + أفاتار + اسم العضو)
- لوحة تحكم بأزرار (/لوحة_تحكم) للترحيب والرسائل التلقائية المتكررة

طريقة التشغيل:
1. pip install -r requirements.txt
2. حط DISCORD_TOKEN بمتغيرات البيئة (Secrets / Environment Variables)
3. python bot.py
"""

import os
import io
import sqlite3
import random
import logging
import asyncio
from datetime import datetime, timedelta, timezone

import aiohttp
import discord
from discord import app_commands
from discord.ext import tasks
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont, ImageOps

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "bot_data.db")
BACKGROUND_PATH = os.path.join(BASE_DIR, "assets", "background.jpg")
FONT_PATH = os.path.join(BASE_DIR, "assets", "font.ttf")
FONT_URL = "https://github.com/google/fonts/raw/main/ofl/tajawal/Tajawal-Bold.ttf"

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("level-welcome-bot")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.presences = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# ---------------------------------------------------------------------------
# قاعدة البيانات
# ---------------------------------------------------------------------------

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    cur = conn.cursor()
    cur.execute(
        """CREATE TABLE IF NOT EXISTS levels (
            guild_id TEXT, user_id TEXT, xp INTEGER DEFAULT 0, level INTEGER DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS settings (
            guild_id TEXT PRIMARY KEY,
            welcome_channel_id TEXT,
            welcome_message TEXT
        )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS auto_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT,
            channel_id TEXT,
            message TEXT,
            interval_minutes INTEGER,
            last_sent TEXT
        )"""
    )
    cur.execute(
        """CREATE TABLE IF NOT EXISTS watch_online (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id TEXT,
            user_id TEXT,
            channel_id TEXT
        )"""
    )
    conn.commit()
    conn.close()


DEFAULT_WELCOME = "🎉 هلا وغلا {user} بسيرفر **{server}**! نورتنا 🌟"


def get_settings(guild_id: int) -> dict:
    conn = db()
    row = conn.execute(
        "SELECT * FROM settings WHERE guild_id = ?", (str(guild_id),)
    ).fetchone()
    conn.close()
    if row:
        return dict(row)
    return {"guild_id": str(guild_id), "welcome_channel_id": None, "welcome_message": DEFAULT_WELCOME}


def set_setting(guild_id: int, **kwargs):
    current = get_settings(guild_id)
    current.update({k: v for k, v in kwargs.items() if v is not None})
    conn = db()
    conn.execute(
        """INSERT INTO settings (guild_id, welcome_channel_id, welcome_message)
           VALUES (?, ?, ?)
           ON CONFLICT(guild_id) DO UPDATE SET
             welcome_channel_id = excluded.welcome_channel_id,
             welcome_message = excluded.welcome_message""",
        (str(guild_id), current.get("welcome_channel_id"), current.get("welcome_message")),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# نظام اللفل
# ---------------------------------------------------------------------------

def xp_needed(level: int) -> int:
    return 5 * (level ** 2) + 50 * level + 100


def get_level_row(guild_id: int, user_id: int) -> dict:
    conn = db()
    row = conn.execute(
        "SELECT * FROM levels WHERE guild_id = ? AND user_id = ?",
        (str(guild_id), str(user_id)),
    ).fetchone()
    conn.close()
    if row:
        return dict(row)
    return {"guild_id": str(guild_id), "user_id": str(user_id), "xp": 0, "level": 0}


def save_level_row(guild_id: int, user_id: int, xp: int, level: int):
    conn = db()
    conn.execute(
        """INSERT INTO levels (guild_id, user_id, xp, level) VALUES (?, ?, ?, ?)
           ON CONFLICT(guild_id, user_id) DO UPDATE SET xp = excluded.xp, level = excluded.level""",
        (str(guild_id), str(user_id), xp, level),
    )
    conn.commit()
    conn.close()


def add_xp(guild_id: int, user_id: int, amount: int) -> tuple[int, int, bool]:
    """يضيف XP ويرجع (اللفل الجديد، XP المتبقي، هل صار لفل جديد)."""
    row = get_level_row(guild_id, user_id)
    xp = row["xp"] + amount
    level = row["level"]
    leveled_up = False
    while xp >= xp_needed(level):
        xp -= xp_needed(level)
        level += 1
        leveled_up = True
    save_level_row(guild_id, user_id, xp, level)
    return level, xp, leveled_up


def set_level_direct(guild_id: int, user_id: int, level: int):
    """يحدد لفل عضو مباشرة (للمالك/الأدمن) بدون المرور بنظام الـ XP التدريجي."""
    save_level_row(guild_id, user_id, 0, max(0, level))


def get_leaderboard(guild_id: int, limit: int = 10) -> list[dict]:
    conn = db()
    rows = conn.execute(
        """SELECT * FROM levels WHERE guild_id = ?
           ORDER BY level DESC, xp DESC LIMIT ?""",
        (str(guild_id), limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_rank_position(guild_id: int, user_id: int) -> int:
    conn = db()
    rows = conn.execute(
        """SELECT user_id FROM levels WHERE guild_id = ?
           ORDER BY level DESC, xp DESC""",
        (str(guild_id),),
    ).fetchall()
    conn.close()
    ids = [r["user_id"] for r in rows]
    try:
        return ids.index(str(user_id)) + 1
    except ValueError:
        return len(ids) + 1


def get_watch_list(guild_id: int) -> list[dict]:
    conn = db()
    rows = conn.execute(
        "SELECT * FROM watch_online WHERE guild_id = ?", (str(guild_id),)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_watch(guild_id: int, user_id: int, channel_id: int):
    conn = db()
    conn.execute(
        "INSERT INTO watch_online (guild_id, user_id, channel_id) VALUES (?, ?, ?)",
        (str(guild_id), str(user_id), str(channel_id)),
    )
    conn.commit()
    conn.close()


def remove_watch(watch_id: int):
    conn = db()
    conn.execute("DELETE FROM watch_online WHERE id = ?", (watch_id,))
    conn.commit()
    conn.close()


STATUS_EMOJI = {
    discord.Status.online: "🟢",
    discord.Status.idle: "🌙",
    discord.Status.dnd: "⛔",
    discord.Status.offline: "⚫",
    discord.Status.invisible: "⚫",
}


def count_online(guild: discord.Guild) -> int:
    return sum(
        1
        for m in guild.members
        if not m.bot and m.status != discord.Status.offline
    )


# كولداون كسب XP بالذاكرة (ما يحتاج يبقى محفوظ بعد إعادة التشغيل)
_xp_cooldowns: dict[tuple[int, int], datetime] = {}
XP_COOLDOWN_SECONDS = 60


@client.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    key = (message.guild.id, message.author.id)
    now = datetime.now(timezone.utc)
    last = _xp_cooldowns.get(key)
    if not last or (now - last).total_seconds() >= XP_COOLDOWN_SECONDS:
        _xp_cooldowns[key] = now
        amount = random.randint(15, 25)
        new_level, _, leveled_up = add_xp(message.guild.id, message.author.id, amount)
        if leveled_up:
            try:
                await message.channel.send(
                    f"🎊 مبروك {message.author.mention}! وصلت للفل **{new_level}**"
                )
            except discord.HTTPException:
                pass


# ---------------------------------------------------------------------------
# الترحيب بالأعضاء الجدد
# ---------------------------------------------------------------------------

@client.event
async def on_member_join(member: discord.Member):
    settings = get_settings(member.guild.id)
    channel_id = settings.get("welcome_channel_id")
    if not channel_id:
        return
    channel = member.guild.get_channel(int(channel_id))
    if not channel:
        return

    text = (settings.get("welcome_message") or DEFAULT_WELCOME).format(
        user=member.mention,
        username=member.display_name,
        server=member.guild.name,
        member_count=member.guild.member_count,
    )
    try:
        file = await generate_profile_card(member)
        await channel.send(content=text, file=file)
    except Exception:  # noqa: BLE001
        log.exception("فشل توليد بطاقة الترحيب، إرسال نص بس")
        await channel.send(content=text)


@client.event
async def on_presence_update(before: discord.Member, after: discord.Member):
    # نهتم فقط بالانتقال من "غير متصل" إلى أي حالة اتصال
    if before.status != discord.Status.offline or after.status == discord.Status.offline:
        return

    watch_rows = get_watch_list(after.guild.id)
    for row in watch_rows:
        if row["user_id"] != str(after.id):
            continue
        channel = after.guild.get_channel(int(row["channel_id"]))
        if channel:
            try:
                await channel.send(f"🟢 {after.mention} دخل أونلاين الحين!")
            except discord.HTTPException:
                pass


# ---------------------------------------------------------------------------
# توليد بطاقة الصورة (/افتار + بطاقة الترحيب)
# ---------------------------------------------------------------------------

CARD_WIDTH, CARD_HEIGHT = 900, 300
AVATAR_SIZE = 180

_font_ready = asyncio.Lock()


async def ensure_font():
    if os.path.exists(FONT_PATH):
        return
    async with _font_ready:
        if os.path.exists(FONT_PATH):
            return
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(FONT_URL, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        os.makedirs(os.path.dirname(FONT_PATH), exist_ok=True)
                        with open(FONT_PATH, "wb") as f:
                            f.write(data)
        except Exception:  # noqa: BLE001
            log.warning("ما قدرت أحمل الخط العربي، بنستخدم خط افتراضي")


def get_font(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except Exception:  # noqa: BLE001
        try:
            return ImageFont.load_default(size=size)
        except TypeError:
            return ImageFont.load_default()


def make_circle_avatar(avatar_bytes: bytes, size: int) -> Image.Image:
    img = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((size, size))
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size, size), fill=255)
    circular = Image.new("RGBA", (size, size))
    circular.paste(img, (0, 0), mask)

    # إطار أبيض حول الصورة
    bordered = Image.new("RGBA", (size + 10, size + 10), (0, 0, 0, 0))
    draw2 = ImageDraw.Draw(bordered)
    draw2.ellipse((0, 0, size + 10, size + 10), fill=(255, 255, 255, 255))
    bordered.paste(circular, (5, 5), circular)
    return bordered


async def generate_profile_card(member: discord.Member) -> discord.File:
    await ensure_font()

    bg = Image.open(BACKGROUND_PATH).convert("RGB")
    bg = ImageOps.fit(bg, (CARD_WIDTH, CARD_HEIGHT), method=Image.LANCZOS)
    card = bg.convert("RGBA")

    # طبقة تعتيم شفافة لتحسين وضوح النص
    overlay = Image.new("RGBA", card.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rectangle((0, CARD_HEIGHT - 150, CARD_WIDTH, CARD_HEIGHT), fill=(0, 0, 0, 140))
    card = Image.alpha_composite(card, overlay)

    # تحميل الأفاتار
    avatar_url = member.display_avatar.replace(size=256).url
    async with aiohttp.ClientSession() as session:
        async with session.get(avatar_url) as resp:
            avatar_bytes = await resp.read()

    avatar_img = make_circle_avatar(avatar_bytes, AVATAR_SIZE)
    avatar_pos = (40, CARD_HEIGHT - AVATAR_SIZE - 10 - 40)
    card.paste(avatar_img, avatar_pos, avatar_img)

    draw = ImageDraw.Draw(card)
    name_font = get_font(46)
    sub_font = get_font(24)

    text_x = avatar_pos[0] + AVATAR_SIZE + 40
    text_y = CARD_HEIGHT - 150

    status_emoji = STATUS_EMOJI.get(member.status, "⚫")
    online_count = count_online(member.guild)

    draw.text((text_x, text_y + 15), member.display_name, font=name_font, fill="white")
    draw.text(
        (text_x, text_y + 75),
        f"{status_emoji} عضو في {member.guild.name} — 🟢 {online_count} متصل الآن",
        font=sub_font,
        fill=(220, 220, 220, 255),
    )

    buffer = io.BytesIO()
    card.convert("RGB").save(buffer, format="PNG")
    buffer.seek(0)
    return discord.File(buffer, filename="profile_card.png")


# ---------------------------------------------------------------------------
# أوامر Slash
# ---------------------------------------------------------------------------

def is_admin(interaction: discord.Interaction) -> bool:
    return bool(interaction.user.guild_permissions.administrator)


async def admin_only_check(interaction: discord.Interaction) -> bool:
    if not is_admin(interaction):
        await interaction.response.send_message(
            "⛔ هذا الأمر للأدمن/المالك فقط.", ephemeral=True
        )
        return False
    return True


@tree.command(name="رتبتي", description="يعرض لفلك ونقاط الـ XP الحالية")
async def rank_cmd(interaction: discord.Interaction, عضو: discord.Member | None = None):
    member = عضو or interaction.user
    row = get_level_row(interaction.guild.id, member.id)
    pos = get_rank_position(interaction.guild.id, member.id)
    needed = xp_needed(row["level"])
    embed = discord.Embed(
        title=f"رتبة {member.display_name}",
        color=discord.Color.gold(),
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="🏅 اللفل", value=str(row["level"]), inline=True)
    embed.add_field(name="⭐ XP", value=f"{row['xp']}/{needed}", inline=True)
    embed.add_field(name="📊 الترتيب", value=f"#{pos}", inline=True)
    await interaction.response.send_message(embed=embed)


@tree.command(name="المتصدرين", description="يعرض أفضل 10 أعضاء بالسيرفر")
async def leaderboard_cmd(interaction: discord.Interaction):
    rows = get_leaderboard(interaction.guild.id, 10)
    if not rows:
        await interaction.response.send_message("ما فيه بيانات لفل حتى الآن.")
        return
    lines = []
    for i, row in enumerate(rows, start=1):
        member = interaction.guild.get_member(int(row["user_id"]))
        name = member.display_name if member else f"<@{row['user_id']}>"
        lines.append(f"**{i}.** {name} — لفل {row['level']} ({row['xp']} XP)")
    embed = discord.Embed(
        title="🏆 المتصدرين",
        description="\n".join(lines),
        color=discord.Color.blurple(),
    )
    await interaction.response.send_message(embed=embed)


@tree.command(name="المتصلين", description="يعرض الأعضاء المتصلين الآن بالسيرفر")
async def online_members_cmd(interaction: discord.Interaction):
    guild = interaction.guild
    groups: dict[discord.Status, list[str]] = {
        discord.Status.online: [],
        discord.Status.idle: [],
        discord.Status.dnd: [],
    }
    for member in guild.members:
        if member.bot:
            continue
        if member.status in groups:
            groups[member.status].append(member.display_name)

    total = sum(len(v) for v in groups.values())
    embed = discord.Embed(
        title=f"🟢 المتصلين الآن ({total})",
        color=discord.Color.green(),
    )
    labels = {
        discord.Status.online: "🟢 متصل",
        discord.Status.idle: "🌙 خامل",
        discord.Status.dnd: "⛔ مشغول",
    }
    for status, names in groups.items():
        if not names:
            continue
        preview = ", ".join(names[:25])
        if len(names) > 25:
            preview += f" ... (+{len(names) - 25})"
        embed.add_field(name=f"{labels[status]} ({len(names)})", value=preview, inline=False)

    if total == 0:
        embed.description = "ما فيه أي عضو متصل حالياً."
    await interaction.response.send_message(embed=embed)


@tree.command(name="تحديد_لفل", description="[أدمن] يحدد لفل عضو مباشرة")
@app_commands.describe(عضو="العضو", اللفل="اللفل الجديد")
async def set_level_cmd(interaction: discord.Interaction, عضو: discord.Member, اللفل: int):
    if not await admin_only_check(interaction):
        return
    set_level_direct(interaction.guild.id, عضو.id, اللفل)
    await interaction.response.send_message(
        f"✅ تم تحديد لفل {عضو.mention} إلى **{اللفل}**."
    )


@tree.command(name="اضف_اكسبي", description="[أدمن] يضيف كمية XP لعضو")
@app_commands.describe(عضو="العضو", الكمية="كمية الـ XP المراد إضافتها")
async def add_xp_cmd(interaction: discord.Interaction, عضو: discord.Member, الكمية: int):
    if not await admin_only_check(interaction):
        return
    new_level, remaining, leveled_up = add_xp(interaction.guild.id, عضو.id, الكمية)
    msg = f"✅ تمت إضافة {الكمية} XP لـ {عضو.mention}."
    if leveled_up:
        msg += f" (صار لفل {new_level} 🎉)"
    await interaction.response.send_message(msg)


@tree.command(name="افتار", description="يطلع بطاقة فيها صورتك أو صورة عضو آخر")
@app_commands.describe(عضو="اختياري: عضو ثاني غيرك")
async def avatar_cmd(interaction: discord.Interaction, عضو: discord.Member | None = None):
    await interaction.response.defer(thinking=True)
    member = عضو or interaction.user
    try:
        file = await generate_profile_card(member)
    except Exception as exc:  # noqa: BLE001
        log.exception("فشل توليد بطاقة الأفاتار")
        await interaction.followup.send(f"❌ صار خطأ أثناء توليد البطاقة: {exc}")
        return
    await interaction.followup.send(file=file)


# ---------------------------------------------------------------------------
# لوحة التحكم (أزرار + نوافذ إدخال)
# ---------------------------------------------------------------------------

class WelcomeMessageModal(discord.ui.Modal, title="تعديل رسالة الترحيب"):
    message_input = discord.ui.TextInput(
        label="رسالة الترحيب",
        style=discord.TextStyle.paragraph,
        placeholder="استخدم {user} للمنشن، {username} للاسم، {server} لاسم السيرفر",
        default=DEFAULT_WELCOME,
        max_length=500,
    )

    def __init__(self, guild_id: int):
        super().__init__()
        self.guild_id = guild_id
        current = get_settings(guild_id).get("welcome_message")
        if current:
            self.message_input.default = current

    async def on_submit(self, interaction: discord.Interaction):
        set_setting(self.guild_id, welcome_message=str(self.message_input.value))
        await interaction.response.send_message("✅ تم تحديث رسالة الترحيب.", ephemeral=True)


class WelcomeChannelSelect(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(
            placeholder="اختر قناة الترحيب",
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1,
        )

    async def callback(self, interaction: discord.Interaction):
        channel = self.values[0]
        set_setting(interaction.guild.id, welcome_channel_id=str(channel.id))
        await interaction.response.send_message(
            f"✅ تم تحديد قناة الترحيب: {channel.mention}", ephemeral=True
        )


class WelcomeChannelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=120)
        self.add_item(WelcomeChannelSelect())


class AutoMessageModal(discord.ui.Modal, title="إضافة رسالة تلقائية متكررة"):
    channel_input = discord.ui.TextInput(
        label="منشن القناة أو الآيدي",
        placeholder="#general أو 123456789012345678",
    )
    message_input = discord.ui.TextInput(
        label="نص الرسالة",
        style=discord.TextStyle.paragraph,
        max_length=1500,
    )
    interval_input = discord.ui.TextInput(
        label="كل كم دقيقة تتكرر؟",
        placeholder="مثال: 60 (يعني كل ساعة)",
    )

    def __init__(self, guild: discord.Guild):
        super().__init__()
        self.guild = guild

    async def on_submit(self, interaction: discord.Interaction):
        raw_channel = str(self.channel_input.value).strip()
        channel_id = raw_channel.strip("<#>")
        channel = self.guild.get_channel_or_thread(int(channel_id)) if channel_id.isdigit() else None
        if not channel:
            await interaction.response.send_message(
                "⚠️ ما قدرت ألقى القناة. تأكد إنك كاتب منشن صحيح (#القناة) أو آيدي صحيح.",
                ephemeral=True,
            )
            return
        try:
            interval = int(str(self.interval_input.value).strip())
            if interval < 1:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                "⚠️ عدد الدقائق لازم يكون رقم صحيح أكبر من صفر.", ephemeral=True
            )
            return

        conn = db()
        conn.execute(
            """INSERT INTO auto_messages (guild_id, channel_id, message, interval_minutes, last_sent)
               VALUES (?, ?, ?, ?, NULL)""",
            (str(self.guild.id), str(channel.id), str(self.message_input.value), interval),
        )
        conn.commit()
        conn.close()

        await interaction.response.send_message(
            f"✅ تمت إضافة رسالة تلقائية بقناة {channel.mention} كل **{interval}** دقيقة.",
            ephemeral=True,
        )


class RemoveAutoMessageSelect(discord.ui.Select):
    def __init__(self, options: list[discord.SelectOption]):
        super().__init__(placeholder="اختر الرسالة المراد حذفها", options=options)

    async def callback(self, interaction: discord.Interaction):
        msg_id = int(self.values[0])
        conn = db()
        conn.execute("DELETE FROM auto_messages WHERE id = ?", (msg_id,))
        conn.commit()
        conn.close()
        await interaction.response.send_message("🗑️ تم حذف الرسالة التلقائية.", ephemeral=True)


class WatchOnlineModal(discord.ui.Modal, title="مراقبة اتصال عضو"):
    user_input = discord.ui.TextInput(
        label="منشن العضو أو الآيدي",
        placeholder="@اسم_العضو أو 123456789012345678",
    )
    channel_input = discord.ui.TextInput(
        label="قناة الإشعار",
        placeholder="#القناة أو آيدي القناة",
    )

    def __init__(self, guild: discord.Guild):
        super().__init__()
        self.guild = guild

    async def on_submit(self, interaction: discord.Interaction):
        user_raw = str(self.user_input.value).strip().strip("<@!>")
        channel_raw = str(self.channel_input.value).strip().strip("<#>")

        if not user_raw.isdigit() or not channel_raw.isdigit():
            await interaction.response.send_message(
                "⚠️ تأكد إنك كاتب منشن أو آيدي صحيح للعضو والقناة.", ephemeral=True
            )
            return

        member = self.guild.get_member(int(user_raw))
        channel = self.guild.get_channel(int(channel_raw))
        if not member or not channel:
            await interaction.response.send_message(
                "⚠️ ما قدرت ألقى العضو أو القناة بالسيرفر.", ephemeral=True
            )
            return

        add_watch(self.guild.id, member.id, channel.id)
        await interaction.response.send_message(
            f"✅ راح أنبهك بقناة {channel.mention} أول ما {member.mention} يدخل أونلاين.",
            ephemeral=True,
        )


class RemoveWatchSelect(discord.ui.Select):
    def __init__(self, options: list[discord.SelectOption]):
        super().__init__(placeholder="اختر المراقبة المراد إلغاؤها", options=options)

    async def callback(self, interaction: discord.Interaction):
        remove_watch(int(self.values[0]))
        await interaction.response.send_message("🗑️ تم إلغاء المراقبة.", ephemeral=True)


class ControlPanelView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=300)
        self.guild_id = guild_id

    @discord.ui.button(label="قناة الترحيب", emoji="🎉", style=discord.ButtonStyle.primary, row=0)
    async def set_welcome_channel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "اختر القناة اللي تبي الترحيب يصير فيها:", view=WelcomeChannelView(), ephemeral=True
        )

    @discord.ui.button(label="رسالة الترحيب", emoji="✏️", style=discord.ButtonStyle.primary, row=0)
    async def set_welcome_message(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(WelcomeMessageModal(self.guild_id))

    @discord.ui.button(label="رسالة تلقائية جديدة", emoji="⏰", style=discord.ButtonStyle.success, row=1)
    async def add_auto_message(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AutoMessageModal(interaction.guild))

    @discord.ui.button(label="عرض الرسائل التلقائية", emoji="📋", style=discord.ButtonStyle.secondary, row=1)
    async def list_auto_messages(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = db()
        rows = conn.execute(
            "SELECT * FROM auto_messages WHERE guild_id = ?", (str(self.guild_id),)
        ).fetchall()
        conn.close()
        if not rows:
            await interaction.response.send_message("ما فيه رسائل تلقائية حالياً.", ephemeral=True)
            return
        lines = []
        for r in rows:
            channel = interaction.guild.get_channel(int(r["channel_id"]))
            ch_name = channel.mention if channel else r["channel_id"]
            preview = r["message"][:40] + ("..." if len(r["message"]) > 40 else "")
            lines.append(f"`#{r['id']}` — {ch_name} — كل {r['interval_minutes']} دقيقة — \"{preview}\"")
        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    @discord.ui.button(label="حذف رسالة تلقائية", emoji="🗑️", style=discord.ButtonStyle.danger, row=1)
    async def remove_auto_message(self, interaction: discord.Interaction, button: discord.ui.Button):
        conn = db()
        rows = conn.execute(
            "SELECT * FROM auto_messages WHERE guild_id = ?", (str(self.guild_id),)
        ).fetchall()
        conn.close()
        if not rows:
            await interaction.response.send_message("ما فيه رسائل تلقائية للحذف.", ephemeral=True)
            return
        options = [
            discord.SelectOption(
                label=f"#{r['id']} - كل {r['interval_minutes']} دقيقة",
                description=r["message"][:90],
                value=str(r["id"]),
            )
            for r in rows
        ]
        view = discord.ui.View(timeout=60)
        view.add_item(RemoveAutoMessageSelect(options))
        await interaction.response.send_message("اختر الرسالة اللي تبي تحذفها:", view=view, ephemeral=True)

    @discord.ui.button(label="مراقبة اتصال عضو", emoji="👀", style=discord.ButtonStyle.primary, row=2)
    async def add_watch_online(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(WatchOnlineModal(interaction.guild))

    @discord.ui.button(label="عرض/حذف المراقبات", emoji="📡", style=discord.ButtonStyle.secondary, row=2)
    async def list_watch_online(self, interaction: discord.Interaction, button: discord.ui.Button):
        rows = get_watch_list(self.guild_id)
        if not rows:
            await interaction.response.send_message("ما فيه أي مراقبة اتصال حالياً.", ephemeral=True)
            return
        options = []
        lines = []
        for r in rows:
            member = interaction.guild.get_member(int(r["user_id"]))
            channel = interaction.guild.get_channel(int(r["channel_id"]))
            name = member.display_name if member else r["user_id"]
            ch_name = channel.mention if channel else r["channel_id"]
            lines.append(f"`#{r['id']}` — {name} ← إشعار بـ {ch_name}")
            options.append(
                discord.SelectOption(label=f"#{r['id']} - {name}", value=str(r["id"]))
            )
        view = discord.ui.View(timeout=60)
        view.add_item(RemoveWatchSelect(options))
        await interaction.response.send_message(
            "\n".join(lines), view=view, ephemeral=True
        )


@tree.command(name="لوحة_تحكم", description="[أدمن] يفتح لوحة تحكم البوت (ترحيب + رسائل تلقائية)")
async def control_panel_cmd(interaction: discord.Interaction):
    if not await admin_only_check(interaction):
        return
    embed = discord.Embed(
        title="🎛️ لوحة تحكم البوت",
        description=(
            "استخدم الأزرار تحت للتحكم بإعدادات الترحيب والرسائل التلقائية المتكررة."
        ),
        color=discord.Color.blurple(),
    )
    await interaction.response.send_message(embed=embed, view=ControlPanelView(interaction.guild.id))


# ---------------------------------------------------------------------------
# مهمة الرسائل التلقائية المتكررة
# ---------------------------------------------------------------------------

@tasks.loop(minutes=1)
async def auto_message_loop():
    conn = db()
    rows = conn.execute("SELECT * FROM auto_messages").fetchall()
    conn.close()

    now = datetime.now(timezone.utc)
    for row in rows:
        last_sent = row["last_sent"]
        due = True
        if last_sent:
            last_dt = datetime.fromisoformat(last_sent)
            due = (now - last_dt) >= timedelta(minutes=row["interval_minutes"])
        if not due:
            continue

        guild = client.get_guild(int(row["guild_id"]))
        if not guild:
            continue
        channel = guild.get_channel(int(row["channel_id"]))
        if not channel:
            continue
        try:
            await channel.send(row["message"])
        except discord.HTTPException:
            log.warning("فشل إرسال رسالة تلقائية بقناة %s", row["channel_id"])
            continue

        conn = db()
        conn.execute(
            "UPDATE auto_messages SET last_sent = ? WHERE id = ?",
            (now.isoformat(), row["id"]),
        )
        conn.commit()
        conn.close()


@auto_message_loop.before_loop
async def before_auto_message_loop():
    await client.wait_until_ready()


# ---------------------------------------------------------------------------
# بدء التشغيل
# ---------------------------------------------------------------------------

@client.event
async def on_ready():
    init_db()
    await tree.sync()
    if not auto_message_loop.is_running():
        auto_message_loop.start()
    log.info("تم تسجيل الدخول باسم %s", client.user)


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("حط توكن البوت في متغير البيئة DISCORD_TOKEN")
    init_db()
    client.run(TOKEN)
