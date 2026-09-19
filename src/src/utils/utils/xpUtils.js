// كم XP يحتاجه العضو عشان يوصل لمستوى معيّن (منحنى تصاعدي بسيط)
function xpForLevel(level) {
  return 5 * level * level + 50 * level + 100;
}

// يحسب اللفل الحالي بناءً على مجموع الـ XP
function levelFromXp(totalXp) {
  let level = 0;
  let remaining = totalXp;
  while (remaining >= xpForLevel(level)) {
    remaining -= xpForLevel(level);
    level++;
  }
  return level;
}

// يرجع: اللفل الحالي، XP داخل اللفل الحالي، XP المطلوب لإكمال اللفل الحالي
function getProgress(totalXp) {
  let level = 0;
  let remaining = totalXp;
  while (remaining >= xpForLevel(level)) {
    remaining -= xpForLevel(level);
    level++;
  }
  return {
    level,
    xpIntoLevel: remaining,
    xpNeeded: xpForLevel(level),
  };
}

function randomXp(min, max) {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

module.exports = { xpForLevel, levelFromXp, getProgress, randomXp };
