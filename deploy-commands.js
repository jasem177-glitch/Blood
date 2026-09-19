require("dotenv").config();
const fs = require("fs");
const path = require("path");
const { REST, Routes } = require("discord.js");

const commands = [];
const commandsPath = path.join(__dirname, "src", "commands");
const commandFiles = fs.readdirSync(commandsPath).filter((f) => f.endsWith(".js"));

for (const file of commandFiles) {
  const command = require(path.join(commandsPath, file));
  commands.push(command.data.toJSON());
}

const rest = new REST().setToken(process.env.DISCORD_TOKEN);

(async () => {
  try {
    console.log(`⏳ يتم تسجيل ${commands.length} أوامر...`);

    const route = process.env.GUILD_ID
      ? Routes.applicationGuildCommands(process.env.CLIENT_ID, process.env.GUILD_ID)
      : Routes.applicationCommands(process.env.CLIENT_ID);

    await rest.put(route, { body: commands });

    console.log("✅ تم تسجيل الأوامر بنجاح!");
    if (process.env.GUILD_ID) {
      console.log("(مسجلة على سيرفر واحد فقط - تظهر فوراً)");
    } else {
      console.log("(مسجلة بشكل عام - قد تاخذ لين ساعة عشان تظهر بكل السيرفرات)");
    }
  } catch (error) {
    console.error("❌ صار خطأ أثناء تسجيل الأوامر:", error);
  }
})();
