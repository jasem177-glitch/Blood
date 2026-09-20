const { SlashCommandBuilder, AttachmentBuilder } = require("discord.js");
const db = require("../database");
const { getProgress } = require("../utils/xpUtils");
const { generateRankCard } = require("../utils/rankCard");
const config = require("../config");

module.exports = {
  data: new SlashCommandBuilder()
    .setName("rank")
    .setDescription("يعرض بطاقة الرانك (المستوى والتقدم)")
    .addUserOption((opt) =>
      opt.setName("العضو").setDescription("العضو اللي تبي تشوف رانكه (اختياري)").setRequired(false)
    ),

  async execute(interaction) {
    await interaction.deferReply();

    const targetUser = interaction.options.getUser("العضو") || interaction.user;
    const targetMember = await interaction.guild.members.fetch(targetUser.id).catch(() => null);
    const displayName = targetMember ? targetMember.displayName : targetUser.username;

    const stats = db.getUser(interaction.guild.id, targetUser.id);
    const { level, xpIntoLevel, xpNeeded } = getProgress(stats.xp);

    const leaderboard = db.getLeaderboard(interaction.guild.id, 1000);
    const rank = leaderboard.findIndex((e) => e.userId === targetUser.id) + 1;

    const avatarUrl = targetUser.displayAvatarURL({ extension: "png", size: 256 });

    const imageBuffer = await generateRankCard({
      username: displayName,
      avatarUrl,
      backgroundUrl: stats.background || config.defaultBackground,
      level,
      rank: rank || leaderboard.length + 1,
      xpIntoLevel,
      xpNeeded,
    });

    const attachment = new AttachmentBuilder(imageBuffer, { name: "rank.png" });
    await interaction.editReply({ files: [attachment] });
  },
};
