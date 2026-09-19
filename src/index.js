require("dotenv").config();
const fs = require("fs");
const path = require("path");
const { Client, GatewayIntentBits, Collection, REST, Routes } = require("discord.js");

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
    GatewayIntentBits.GuildMembers,
  ],
});

// تحميل الأوامر
client.commands = new Collection();
const commandsPath = path.join(__dirname, "commands");
const commandFiles = fs.readdirSync(commandsPath).filter((f) => f.endsWith(".js"));
const commandsData = [];

for (const file of commandFiles) {
  const command = require(path.join(commandsPath, file));
  client.commands.set(command.data.name, command);
  commandsData.push(command.data.toJSON());
}

// تسجيل الأوامر تلقائياً عند كل تشغيل للبوت
async function registerCommands() {
  try {
    const rest = new REST().setToken(process.env.DISCORD_TOKEN);
    console.log(`⏳ يتم تسجيل ${commandsData.length} أوامر تلقائياً...`);
    await rest.put(Routes.applicationCommands(process.env.CLIENT_ID), { body: commandsData });
    console.log("✅ تم تسجيل الأوامر بنجاح!");
  } catch (error) {
    console.error("❌ خطأ أثناء تسجيل الأوامر:", error);
  }
}

// تحميل الأحداث
const eventsPath = path.join(__dirname, "events");
const eventFiles = fs.readdirSync(eventsPath).filter((f) => f.endsWith(".js"));

for (const file of eventFiles) {
  const event = require(path.join(eventsPath, file));
  if (event.once) {
    client.once(event.name, (...args) => event.execute(...args));
  } else {
    client.on(event.name, (...args) => event.execute(...args));
  }
}

// معالجة تفاعل الأوامر (Slash Commands)
client.on("interactionCreate", async (interaction) => {
  if (!interaction.isChatInputCommand()) return;

  const command = client.commands.get(interaction.commandName);
  if (!command) return;

  try {
    await command.execute(interaction);
  } catch (error) {
    console.error(`❌ خطأ في تنفيذ أمر ${interaction.commandName}:`, error);
    const errorMessage = { content: "⚠️ صار خطأ أثناء تنفيذ الأمر.", ephemeral: true };
    if (interaction.replied || interaction.deferred) {
      await interaction.followUp(errorMessage).catch(() => {});
    } else {
      await interaction.reply(errorMessage).catch(() => {});
    }
  }
});

registerCommands();
client.login(process.env.DISCORD_TOKEN);
