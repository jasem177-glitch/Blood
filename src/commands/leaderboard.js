const { SlashCommandBuilder, EmbedBuilder } = require("discord.js");
const db = require("../database");
const { getProgress } = require("../utils/xpUtils");
const config = require("../config");

const MEDALS = ["🥇", "🥈", "🥉"];

module.exports = {
  data: new SlashCommandBuilder()
    .setName("leaderboard")
    .setDescription("يعرض أعلى 10 أعضاء بالسيرفر من حيث اللفل"),

  async execute(interaction) {
    await interaction.deferReply();

    const top = db.getLeaderboard(interaction.guild.id, 10);

    if (top.length === 0) {
      await interaction.editReply("ما فيه بيانات لفل بعد بهذا السيرفر 😅");
      return;
    }

    const lines = await Promise.all(
      top.map(async (entry, i) => {
        const member = await interaction.guild.members.fetch(entry.userId).catch(() => null);
        const name = member ? member.displayName : `عضو غادر (${entry.userId})`;
        const { level } = getProgress(entry.xp);
        const prefix = MEDALS[i] || `**${i + 1}.**`;
        return `${prefix} ${name} — المستوى ${level} (${entry.xp} XP)`;
      })
    );

    const embed = new EmbedBuilder()
      .setTitle(`🏆 ترتيب سيرفر ${interaction.guild.name}`)
      .setColor(config.colors.accent)
      .setDescription(lines.join("\n"))
      .setThumbnail(interaction.guild.iconURL() || null);

    await interaction.editReply({ embeds: [embed] });
  },
};
