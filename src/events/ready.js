module.exports = {
  name: "clientReady",
  once: true,
  execute(client) {
    console.log(`✅ البوت شغال باسم ${client.user.tag}`);
    client.user.setActivity("يراقب اللفلات 📈", { type: 3 }); // Watching
  },
};
