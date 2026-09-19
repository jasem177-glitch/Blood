const { createCanvas, loadImage, GlobalFonts } = require("@napi-rs/canvas");
const config = require("../config");

const WIDTH = 934;
const HEIGHT = 282;

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

async function generateRankCard(opts) {
  const { username, avatarUrl, backgroundUrl, level, rank, xpIntoLevel, xpNeeded } = opts;

  const canvas = createCanvas(WIDTH, HEIGHT);
  const ctx = canvas.getContext("2d");

  roundRect(ctx, 0, 0, WIDTH, HEIGHT, 24);
  ctx.clip();

  if (backgroundUrl) {
    try {
      const bg = await loadImage(backgroundUrl);
      ctx.drawImage(bg, 0, 0, WIDTH, HEIGHT);
      ctx.fillStyle = "rgba(0,0,0,0.45)";
      ctx.fillRect(0, 0, WIDTH, HEIGHT);
    } catch {
      drawGradientBackground(ctx);
    }
  } else {
    drawGradientBackground(ctx);
  }

  const avatarSize = 180;
  const avatarX = 56;
  const avatarY = (HEIGHT - avatarSize) / 2;

  try {
    const avatar = await loadImage(avatarUrl);
    ctx.save();
    ctx.beginPath();
    ctx.arc(avatarX + avatarSize / 2, avatarY + avatarSize / 2, avatarSize / 2 + 6, 0, Math.PI * 2);
    ctx.fillStyle = config.colors.accent;
    ctx.fill();
    ctx.beginPath();
    ctx.arc(avatarX + avatarSize / 2, avatarY + avatarSize / 2, avatarSize / 2, 0, Math.PI * 2);
    ctx.closePath();
    ctx.clip();
    ctx.drawImage(avatar, avatarX, avatarY, avatarSize, avatarSize);
    ctx.restore();
  } catch {
  }

  const textX = avatarX + avatarSize + 40;

  ctx.fillStyle = config.colors.text;
  ctx.font = "bold 42px sans-serif";
  ctx.fillText(username, textX, 110);

  ctx.fillStyle = config.colors.subtext;
  ctx.font = "28px sans-serif";
  ctx.fillText(`المستوى ${level}`, textX, 155);
  ctx.fillText(`الترتيب #${rank}`, textX + 220, 155);

  const barX = textX;
  const barY = 190;
  const barWidth = WIDTH - textX - 56;
  const barHeight = 28;
  const progress = Math.max(0, Math.min(1, xpIntoLevel / xpNeeded));

  roundRect(ctx, barX, barY, barWidth, barHeight, barHeight / 2);
  ctx.fillStyle = config.colors.barBackground;
  ctx.fill();

  if (progress > 0) {
    roundRect(ctx, barX, barY, Math.max(barHeight, barWidth * progress), barHeight, barHeight / 2);
    ctx.fillStyle = config.colors.accent;
    ctx.fill();
  }

  ctx.fillStyle = config.colors.subtext;
  ctx.font = "20px sans-serif";
  ctx.fillText(`${xpIntoLevel} / ${xpNeeded} XP`, barX, barY + barHeight + 30);

  return canvas.encode("png");
}

function drawGradientBackground(ctx) {
  const gradient = ctx.createLinearGradient(0, 0, WIDTH, HEIGHT);
  gradient.addColorStop(0, config.colors.background1);
  gradient.addColorStop(1, config.colors.background2);
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, WIDTH, HEIGHT);
}

module.exports = { generateRankCard };
