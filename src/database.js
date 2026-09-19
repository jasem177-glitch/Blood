const fs = require("fs");
const path = require("path");

const DB_PATH = path.join(__dirname, "..", "data", "levels.json");

function ensureFile() {
  const dir = path.dirname(DB_PATH);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  if (!fs.existsSync(DB_PATH)) fs.writeFileSync(DB_PATH, JSON.stringify({}), "utf8");
}

function readAll() {
  ensureFile();
  const raw = fs.readFileSync(DB_PATH, "utf8");
  try {
    return JSON.parse(raw);
  } catch {
    return {};
  }
}

function writeAll(data) {
  ensureFile();
  fs.writeFileSync(DB_PATH, JSON.stringify(data, null, 2), "utf8");
}

function getUser(guildId, userId) {
  const data = readAll();
  if (!data[guildId]) data[guildId] = {};
  if (!data[guildId][userId]) {
    data[guildId][userId] = { xp: 0, level: 0, lastMessage: 0, background: null };
    writeAll(data);
  }
  return data[guildId][userId];
}

function updateUser(guildId, userId, updates) {
  const data = readAll();
  if (!data[guildId]) data[guildId] = {};
  if (!data[guildId][userId]) data[guildId][userId] = { xp: 0, level: 0, lastMessage: 0, background: null };
  data[guildId][userId] = { ...data[guildId][userId], ...updates };
  writeAll(data);
  return data[guildId][userId];
}

function getLeaderboard(guildId, limit = 10) {
  const data = readAll();
  const guildData = data[guildId] || {};
  return Object.entries(guildData)
    .map(([userId, stats]) => ({ userId, ...stats }))
    .sort((a, b) => b.xp - a.xp)
    .slice(0, limit);
}

module.exports = { getUser, updateUser, getLeaderboard };
