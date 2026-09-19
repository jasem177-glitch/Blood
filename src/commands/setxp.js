const { SlashCommandBuilder } = require("discord.js");
const db = require("../database");
const { levelFromXp } = require("../utils/xpUtils");

module.exports = {
  data: new SlashCommandBuilder()
    .setName("setxp")
    .setDescription("[مالك السيرفر فقط] يحدد الـ XP لعضو معيّن يدوياً")
    .addUserOption((opt) =>
      opt.setName("العضو").setDescription("العضو اللي تبي تعدّل الـ XP حقه").setRequired(true)
    )
    .addIntegerOption((opt) =>
      opt.setName("الكمية").setDescription("قيمة الـ XP الجديدة (رقم صحيح، 0 أو أكبر)").setRequired(true).setMinValue(0)
    ),

  async execute(interaction) {
    // تحقق إن الشخص هو مالك السيرفر فقط
    if (interaction.user.id !== interaction.guild.ownerId) {
      await interaction.reply({
        content: "⛔ هذا الأمر لمالك السيرفر بس.",
        ephemeral: true,
      });
      return;
    }

    const targetUser = interaction.options.getUser("العضو");
    const amount = interaction.options.getInteger("الكمية");

    const newLevel = levelFromXp(amount);

    db.updateUser(interaction.guild.id, targetUser.id, {
      xp: amount,
      level: newLevel,
    });

    await interaction.reply({
      content: `✅ تم تحديث XP حق ${targetUser} إلى **${amount}** (المستوى ${newLevel}).`,
    });
  },
};
