const config = require("../config");
const db = require("../database");
const { levelFromXp, randomXp } = require("../utils/xpUtils");

module.exports = {
  name: "messageCreate",
  async execute(message) {
    if (message.author.bot || !message.guild) return;

    const user = db.getUser(message.guild.id, message.author.id);
    const now = Date.now();
    const cooldownMs = config.cooldownSeconds * 1000;

    if (now - (user.lastMessage || 0) < cooldownMs) return;

    const gainedXp = randomXp(config.minXp, config.maxXp);
    const newXp = user.xp + gainedXp;
    const oldLevel = levelFromXp(user.xp);
    const newLevel = levelFromXp(newXp);

    db.updateUser(message.guild.id, message.author.id, {
      xp: newXp,
      level: newLevel,
      lastMessage: now,
    });

    if (newLevel > oldLevel) {
      message.channel
        .send(`🎉 مبروك ${message.author} ترقيت للمستوى **${newLevel}**!`)
        .catch(() => {});
    }
  },
};
