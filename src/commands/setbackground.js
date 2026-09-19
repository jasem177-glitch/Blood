const { SlashCommandBuilder } = require("discord.js");
const db = require("../database");

module.exports = {
  data: new SlashCommandBuilder()
    .setName("setbackground")
    .setDescription("يغيّر خلفية بطاقة الرانك الخاصة فيك")
    .addStringOption((opt) =>
      opt
        .setName("رابط")
        .setDescription("رابط صورة مباشر (png/jpg). اكتب 'مسح' عشان ترجع للخلفية الافتراضية")
        .setRequired(true)
    ),

  async execute(interaction) {
    const url = interaction.options.getString("رابط");

    if (url === "مسح" || url === "clear") {
      db.updateUser(interaction.guild.id, interaction.user.id, { background: null });
      await interaction.reply({ content: "✅ رجّعنا خلفيتك للوضع الافتراضي.", ephemeral: true });
      return;
    }

    const isValidImageUrl = /^https?:\/\/.+\.(png|jpe?g|webp|gif)(\?.*)?$/i.test(url);
    if (!isValidImageUrl) {
      await interaction.reply({
        content: "⚠️ الرابط لازم يكون رابط صورة مباشر ينتهي بـ png أو jpg أو webp.",
        ephemeral: true,
      });
      return;
    }

    db.updateUser(interaction.guild.id, interaction.user.id, { background: url });
    await interaction.reply({ content: "✅ تم تحديث خلفية بطاقة الرانك الخاصة فيك!", ephemeral: true });
  },
};
