// Settings lookup from the shell config's bar layout — pure logic, probed
// headlessly (test/probe_settings.qml). The service reads its bar-widget
// entry straight out of shell.shellConfig (the omajam pattern), so saved
// changes land without a shell restart and without a widget->service push.
.pragma library

function lookupSettings(config, id) {
  if (!config || !id) return ({});
  var sections = ["left", "center", "right"];
  if (config.bar && config.bar.layout) {
    for (var s = 0; s < sections.length; s++) {
      var list = config.bar.layout[sections[s]];
      if (!Array.isArray(list)) continue;
      for (var i = 0; i < list.length; i++) {
        if (list[i] && String(list[i].id) === id) return list[i];
      }
    }
  }
  if (Array.isArray(config.plugins)) {
    for (var j = 0; j < config.plugins.length; j++) {
      if (config.plugins[j] && String(config.plugins[j].id) === id) return config.plugins[j];
    }
  }
  return ({});
}

function setting(settings, name, fallback) {
  var value = settings ? settings[name] : undefined;
  return value === undefined || value === null ? fallback : value;
}
