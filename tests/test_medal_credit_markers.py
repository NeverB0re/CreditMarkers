"""Medal & Super Credit Markers on PUC Lua 5.1 (lupa) against a fake Chef Shared Loader, plus the built archive."""
import math
import os
import struct
import sys
import tempfile
import unittest

import lupa.lua51 as lua51

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import build  # noqa: E402

CREDIT = "content/env_super_earth/economy_items/super_credit/super_credit_stack"
MEDAL = "hex:773c4184e4bad0df"

FAKE = r"""
local fake = { now = 0, units = {}, loaded = {}, lookups = {}, calls = {}, bitmaps = {}, texts = {}, rects = {} }
os.clock = function() return fake.now end
local function vec(x, y, z) return { _x = x, _y = y, _z = z } end
stingray = {
  Application = {
    can_get = function(kind, name)
      if type(name) == 'table' then return fake.loaded['hex:' .. name.hex] == true end
      return fake.loaded[name] == true
    end,
  },
  IdString64 = { from_hex = function(hex) return { hex = hex } end },
  Vector3 = { x = function(v) return v._x end, y = function(v) return v._y end, z = function(v) return v._z end },
  Script = { temp_byte_count = function() return 7 end, set_temp_byte_count = function(n) fake.temp = n end },
  Gui = { resolution = function() return 1920, 1200 end },
  Window = { show_cursor = function() return fake.cursor == true end },
}
fake.loaded['hex:4d1c334d294dfa97'] = true   -- the avatar, by id: the self-test passes
fake.cam = { x = 0, y = -10, z = 0.8, fx = 0, fy = 1, fz = 0, fov = math.rad(50) }
fake.world, fake.world_id, fake.mission = { name = 'w1' }, 1, true
fake.chef = {
  camera = function() return fake.cam end,
  in_mission = function() return fake.mission end,
  world = function() return fake.world end,
  world_id = function() return fake.world_id end,
  screen = function() return stingray.Gui.resolution() end,
  color = function(r, g, b, a) return { r = r, g = g, b = b, a = a } end,
  own_log = function(name) fake.own_log = name; return true end,
  log = function(fmt, ...)
    local f = assert(io.open(fake.chef.log_directory .. '/' .. (fake.own_log or 'chef_loader') .. '.log', 'a'))
    f:write(string.format(fmt, ...), '\n')
    f:close()
  end,
  rect = function(x, y, w, h, c, layer) fake.rects[#fake.rects + 1] = { x = x, y = y, w = w, h = h, c = c, layer = layer } end,
  bitmap = function(tex, x, y, w, h, c, layer)
    if fake.no_textures then return false end
    fake.bitmaps[#fake.bitmaps + 1] = { tex = tex, x = x, y = y, w = w, h = h, c = c, layer = layer }
    return true
  end,
  text_width = function(s, px) return #s * px / 2 end,
  text = function(x, y, s, px, c) fake.texts[#fake.texts + 1] = { x = x, y = y, s = s, px = px, c = c } end,
  unit_alive = function(u)
    fake.calls.unit_alive = (fake.calls.unit_alive or 0) + 1
    return u.alive ~= false
  end,
  unit_position = function(u)
    fake.calls.unit_position = (fake.calls.unit_position or 0) + 1
    return u.x, u.y, u.z
  end,
  call_kind = function(name, kind, ...)
    fake.calls[name] = (fake.calls[name] or 0) + 1
    if name == 'World.units_by_resource' then
      local world, key = ...
      if type(key) == 'table' then key = 'hex:' .. key.hex end
      assert(fake.loaded[key], 'NATIVE CRASH: looked up a resource that is not loaded: ' .. tostring(key))
      fake.lookups[key] = (fake.lookups[key] or 0) + 1
      if fake.refuse_lookup then return nil, 'refused' end
      return fake.units[key] or {}
    elseif name == 'Unit.box' then
      local u = ...
      if u.box_refused then return nil, 'refused' end
      if u.hidden then return 'POSE', vec(0, 0, 0) end
      return 'POSE', vec(0.3, 0.2, 0.3)
    end
    error('a call the mod has no business making: ' .. name)
  end,
}
fake.options = {}
ModOptionsMenu = {
  register_option = function(id, spec) fake.options[id] = spec; return true end,
  get = function(id) return fake.values and fake.values[id] end,
  on_change = function(id, fn) fake.changed = fake.changed or {}; fake.changed[id] = fn; return true end,
}
function update(dt)
  fake.bitmaps, fake.texts, fake.rects = {}, {}, {}   -- the loader draws what it was given this frame only
end
return fake
"""

TEST_ICONS = "{\n" + "".join("    %s = {%s},\n" % (name, ", ".join("{%d, '%s_%d', %d, %d}" % (s, name, s, s, s)
                                                                  for s in (16, 20, 24, 28, 32, 40, 48, 64)))
                              for name in ("credit", "medal")) + "}"


def unit(x, y=0.0, z=0.0):
    return {"x": x, "y": y, "z": z}


class Case(unittest.TestCase):
    def setUp(self):
        self.lua = lua51.LuaRuntime(unpack_returned_tuples=True)
        self.fake = self.lua.execute(FAKE)
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.fake.chef.log_directory = self.folder.name
        build.ICON_TABLE = TEST_ICONS
        self.source = build.built_source()
        self.mod = None
        self.t = 0.0

    def set_units(self, key, units):
        self.fake.units[key] = self.lua.table(*[self.lua.table_from(u) for u in units])
        self.fake.loaded[key] = True

    def load(self):
        self.mod = self.lua.execute(self.source, self.fake.chef)
        self.assertEqual(self.mod.status, "running", self.log_text())
        return self.mod

    def log_text(self):
        path = os.path.join(self.folder.name, "MedalCreditMarkers.log")
        if not os.path.exists(path):
            return ""
        with open(path, encoding="utf-8") as f:
            return f.read()

    def run_for(self, seconds, step=1 / 60):
        # (markers are worked out 4 times a second: give a change 0.3 s to show)
        update = self.lua.globals().update
        for _ in range(int(seconds / step)):
            self.t += step
            self.fake.now = self.t
            update(0.016)

    def settle(self):
        self.run_for(11.0, step=0.5)    # the start-up grace; the world first seen
        self.run_for(8.5, step=0.5)     # it settled
        self.run_for(3.0)               # every resource looked up, every unit read

    def bitmaps(self):
        return list(self.fake.bitmaps.values())

    def texts(self):
        return list(self.fake.texts.values())

    def dots(self):
        return list(self.mod.dots.values()) if self.mod.dots else []


class Markers(Case):
    def test_medals_and_credits_get_their_icons_and_distance_above(self):
        self.set_units(CREDIT, [unit(-5, 30)])
        self.set_units(MEDAL, [unit(5, 90)])
        self.load()
        self.settle()
        shown = {b.tex.split("_")[0]: b for b in self.bitmaps()}
        self.assertEqual(set(shown), {"credit", "medal"})
        self.assertEqual({b.layer for b in self.bitmaps()}, {900})
        texts = {t.s: t for t in self.texts()}
        self.assertEqual(set(texts), {"%dm" % round(math.hypot(5, 40)), "%dm" % round(math.hypot(5, 100))})
        near = texts["%dm" % round(math.hypot(5, 40))]
        self.assertEqual((near.c.r, near.c.g, near.c.b), (144, 213, 246))        # in its icon's colour
        far = texts["%dm" % round(math.hypot(5, 100))]
        self.assertEqual((far.c.r, far.c.g, far.c.b), (255, 221, 31))
        self.assertGreater(near.y, shown["credit"].y + shown["credit"].h)        # above its icon
        self.assertEqual(len(self.texts()), 8)                                   # bold: four each

    def test_distance_is_across_the_ground_so_it_works_from_a_hellpod(self):
        self.set_units(MEDAL, [unit(0, 200)])
        self.load()
        self.settle()
        self.fake.cam = self.lua.table_from({"x": 0, "y": -10, "z": 490, "fx": 0, "fy": 0.7, "fz": -0.714,
                                             "fov": math.radians(50)})
        self.run_for(0.3)
        (d,) = self.dots()
        self.assertAlmostEqual(d[4], 210, places=3)

    def test_by_default_the_whole_map_is_marked_up_close_too(self):
        self.set_units(CREDIT, [unit(0, -9), unit(0, 1900), unit(0, 2100)])   # 1 m; 1910 m; 2110 m
        self.load()
        self.settle()
        self.assertEqual(sorted(round(d[4]) for d in self.dots()), [1, 1910])
        spec = self.fake.options["medal_credit_markers.range"]
        self.assertEqual((spec.default, spec.max), (2000, 2000))

    def test_the_range_is_a_setting(self):
        self.set_units(CREDIT, [unit(0, 100), unit(0, 400)])                  # 110 m; 410 m
        self.load()
        self.settle()
        self.fake.changed["medal_credit_markers.range"](200)
        self.run_for(0.3)
        self.assertEqual(sorted(round(d[4]) for d in self.dots()), [110])

    def test_each_kind_and_the_distance_can_be_turned_off(self):
        self.set_units(CREDIT, [unit(-5, 30)])
        self.set_units(MEDAL, [unit(5, 30)])
        self.load()
        self.settle()
        self.fake.changed["medal_credit_markers.show_medal"](False)
        self.run_for(0.3)
        self.assertEqual([b.tex.split("_")[0] for b in self.bitmaps()], ["credit"])
        self.fake.changed["medal_credit_markers.distance"](False)
        self.run_for(0.1)
        self.assertEqual(self.texts(), [])
        self.assertEqual(set(self.fake.options.keys()), {"medal_credit_markers." + n for n in
                         ("show_medal", "show_credit", "range", "distance")})

    def test_only_the_nearest_are_drawn(self):
        self.set_units(CREDIT, [unit(0, 20 + i) for i in range(50)])
        self.load()
        self.settle()
        self.assertEqual(len(self.dots()), 30)
        self.assertLess(max(d[4] for d in self.dots()), 61)

    def test_the_icon_grows_with_the_screen_and_shrinks_with_distance(self):
        self.set_units(CREDIT, [unit(0, 10)])
        self.load()
        self.settle()
        (near,) = self.bitmaps()
        self.assertAlmostEqual(near.h, 30, delta=0.01)
        self.fake.units[CREDIT][1].y = 490                                 # 500 m: and from there on
        self.run_for(0.5)
        (far,) = self.bitmaps()
        self.assertAlmostEqual(far.h, 30 * 0.7, delta=0.01)
        self.lua.execute("stingray.Gui.resolution = function() return 2560, 1440 end")
        self.run_for(0.1)
        (big,) = self.bitmaps()
        self.assertAlmostEqual(big.h, 30 * 0.7 * 1440 / 1080, delta=0.01)

    def test_behind_the_camera_or_off_screen_nothing_is_drawn(self):
        self.set_units(CREDIT, [unit(0, -40), unit(250, 0)])
        self.load()
        self.settle()
        self.assertEqual(len(self.dots()), 2)
        self.assertEqual(self.bitmaps(), [])

    def test_a_texture_that_cant_be_drawn_gets_a_square_and_a_note(self):
        self.fake.no_textures = True
        self.set_units(MEDAL, [unit(0, 30)])
        self.load()
        self.settle()
        self.assertEqual(len(list(self.fake.rects.values())), 1)
        self.assertEqual(self.log_text().count("could not be drawn"), 1)

    def test_markers_hide_while_the_cursor_shows(self):
        self.set_units(CREDIT, [unit(0, 30)])
        self.load()
        self.settle()
        self.fake.cursor = True
        self.run_for(0.1)
        self.assertEqual(self.bitmaps(), [])
        self.fake.cursor = False
        self.run_for(0.1)
        self.assertEqual(len(self.bitmaps()), 1)


class Lifecycle(Case):
    def test_a_unit_gone_loses_its_marker(self):
        self.set_units(CREDIT, [unit(0, 30)])
        self.load()
        self.settle()
        self.assertEqual(len(self.dots()), 1)
        self.fake.units[CREDIT][1].alive = False                           # still listed, gone
        self.run_for(0.5)
        self.assertEqual(self.dots(), [])

    def test_a_unit_that_stops_showing_is_hidden_and_may_come_back(self):
        self.set_units(MEDAL, [unit(0, 30)])
        self.load()
        self.settle()
        u = self.fake.units[MEDAL][1]
        u.hidden = True                                                    # picked up, the unit stays
        self.run_for(1.5)
        self.assertEqual(self.dots(), [])
        self.assertIn("shows nothing any more", self.log_text())
        u.hidden = False
        self.run_for(1.5)
        self.assertEqual(len(self.dots()), 1)

    def test_a_unit_never_seen_showing_keeps_its_marker(self):
        u = unit(0, 30)
        u["hidden"] = True                                                 # not ready yet: no conclusion from that
        self.set_units(MEDAL, [u])
        self.load()
        self.settle()
        self.assertEqual(len(self.dots()), 1)

    def test_a_refused_answer_changes_nothing(self):
        self.set_units(MEDAL, [unit(0, 30)])
        self.load()
        self.settle()
        u = self.fake.units[MEDAL][1]
        u.box_refused = True
        self.run_for(1.5)
        self.assertEqual(len(self.dots()), 1)
        u.box_refused, u.hidden = None, True
        self.run_for(1.5)
        self.assertEqual(self.dots(), [])
        u.box_refused = True
        self.run_for(1.5)
        self.assertEqual(self.dots(), [])
        self.fake.refuse_lookup = True                                     # a refused look isn't an empty one
        u.hidden, u.box_refused = False, None
        self.run_for(1.5)
        self.assertEqual(len(self.dots()), 1)
        self.assertIn("lookup failed", self.log_text())

    def test_new_item_in_the_old_ones_place_gets_its_marker(self):
        self.set_units(MEDAL, [unit(0, 30)])
        self.load()
        self.settle()
        self.fake.units[MEDAL][1].hidden = True
        self.run_for(1.5)
        self.assertEqual(self.dots(), [])
        self.set_units(MEDAL, [unit(0, 30)])                               # another unit
        self.run_for(2.0)
        self.assertEqual(len(self.dots()), 1)

    def test_not_in_a_mission_nothing_is_looked_up(self):
        self.set_units(CREDIT, [unit(0, 30)])
        self.fake.mission = False
        self.load()
        self.settle()
        self.assertEqual(len(self.fake.lookups), 0)
        self.assertEqual(self.bitmaps(), [])

    def test_leaving_the_mission_clears_markers(self):
        self.set_units(CREDIT, [unit(0, 30)])
        self.load()
        self.settle()
        self.fake.mission = False
        self.run_for(0.1)
        self.assertEqual(self.bitmaps(), [])
        self.assertEqual(self.dots(), [])

    def test_a_new_world_forgets_and_waits_for_it_to_settle(self):
        self.set_units(CREDIT, [unit(0, 30)])
        self.load()
        self.settle()
        before = self.fake.lookups[CREDIT]
        self.fake.world_id = 2
        self.run_for(5.0)
        self.assertEqual(self.dots(), [])
        self.assertEqual(self.fake.lookups[CREDIT], before)
        self.run_for(6.0)
        self.assertEqual(len(self.dots()), 1)

    def test_no_world_is_quiet(self):
        self.set_units(CREDIT, [unit(0, 30)])
        self.load()
        self.settle()
        self.fake.world = None
        self.run_for(1.0)
        self.assertEqual(self.bitmaps(), [])
        self.assertNotIn("failed", self.log_text())

    def test_waits_after_start_up(self):
        self.set_units(CREDIT, [unit(0, 30)])
        self.load()
        self.run_for(9.0, step=0.5)
        self.assertEqual(len(self.fake.lookups), 0)

    def test_unloaded_resources_are_never_looked_up(self):
        self.set_units(CREDIT, [unit(0, 30)])                              # the fake crashes if any other is asked
        self.load()
        self.settle()
        self.run_for(5.0)
        self.assertEqual(set(self.fake.lookups.keys()), {CREDIT})
        self.assertNotIn("failed", self.log_text())

    def test_when_the_id_self_test_fails_the_medal_stays_off(self):
        self.fake.loaded["hex:4d1c334d294dfa97"] = None
        self.set_units(MEDAL, [unit(0, 30)])
        self.set_units(CREDIT, [unit(5, 30)])
        self.load()
        self.settle()
        self.assertEqual([b.tex.split("_")[0] for b in self.bitmaps()], ["credit"])
        self.assertIn("the medal stays off", self.log_text())

    def test_the_engine_is_asked_little(self):
        self.set_units(CREDIT, [unit(-1, 30), unit(1, 30)])
        self.set_units(MEDAL, [unit(0, 40)])
        self.load()
        self.settle()
        self.fake.calls = self.lua.table()
        self.run_for(10.0)                                                 # 600 frames, 3 units, 2 resources
        calls = self.fake.calls
        self.assertLessEqual(calls["World.units_by_resource"], 11 * 2 + 1)  # two loaded, once a second each
        self.assertLessEqual(calls.unit_position, 3 * 4 * 10 + 3)          # 4 times a second each
        self.assertLessEqual(calls["Unit.box"], 3 * 10 + 3)                # once a second each

    def test_a_drawing_failure_skips_that_frame_only(self):
        self.set_units(CREDIT, [unit(0, 30)])
        self.load()
        self.settle()
        self.lua.execute("""local fake = ...
            local width = fake.chef.text_width
            fake.fail_left = 2
            fake.chef.text_width = function(...)
              if fake.fail_left > 0 then fake.fail_left = fake.fail_left - 1; error('a passing failure') end
              return width(...)
            end""", self.fake)
        self.run_for(0.2)
        self.assertEqual(len(self.bitmaps()), 1)
        self.assertIn("tick failed", self.log_text())
        self.assertFalse(self.mod.disabled)

    def test_the_log_is_the_loaders_own_for_this_mod_and_no_file_is_opened(self):
        self.load()
        self.assertEqual(self.fake.own_log, "MedalCreditMarkers")
        self.assertIn("1.0.0 loading", self.log_text())
        with open(build.SOURCE, encoding="utf-8") as f:
            source = f.read()
        self.assertNotIn("io.open", source)                                # (Chef 1.4 refuses a mod its old logs)

    def test_the_log_says_so_when_one_goes(self):
        self.set_units(MEDAL, [unit(0, 30), unit(5, 30)])
        self.load()
        self.settle()
        self.fake.units[MEDAL][1].alive = False
        self.run_for(0.5)
        self.assertEqual(self.log_text().count("medal: one is gone"), 1)

    def test_without_chef_it_stays_off_and_says_why(self):
        mod = self.lua.execute(self.source)
        self.assertEqual(mod.status, "no Chef Shared Loader")
        self.lua.execute("local fake = ...; fake.chef.bitmap = nil; MedalCreditMarkers = nil", self.fake)
        mod = self.lua.execute(self.source, self.fake.chef)
        self.assertEqual(mod.status, "Chef Shared Loader without bitmap (too old?)")

    def test_loads_once(self):
        first = self.load()
        second = self.lua.execute(self.source, self.fake.chef)
        self.assertTrue(self.lua.globals().rawequal(first, second))


class Separation(unittest.TestCase):
    """Nothing it shares with Extended Pickup Icons Range, which runs beside it."""

    def test_nothing_is_shared_with_the_sister_mod(self):
        with open(build.SOURCE, encoding="utf-8") as f:
            source = f.read()
        self.assertIn("local MOD_KEY = 'MedalCreditMarkers'", source)
        for theirs in ("ExtendedPickupIconsRange", "pickup_dots", "extended_pickup_icons_range"):
            self.assertNotIn(theirs, source)
        self.assertNotEqual(build.MANIFEST["Guid"], "453493d3-ffa7-4148-9b30-d6e4ab32b9d1")
        self.assertNotEqual(build.RESOURCE, "mods/codex/extended_pickup_icons_range")

    def test_it_makes_no_risky_calls(self):
        with open(build.SOURCE, encoding="utf-8") as f:
            source = "".join(line.split("--")[0] + chr(10) for line in f)   # the code, not what its comments tell
        for risky in ("unit_node", "has_node", "animation", "Mesh.", "Unit.mesh", "World.units'", "require", "ffi"):
            self.assertNotIn(risky, source, risky)


class Archive(unittest.TestCase):
    def test_the_archive_holds_the_lua_and_every_icon(self):
        textures, table = build.icon_textures()
        self.assertEqual(len(textures), 16)
        self.assertEqual({t[0].split("/")[-1].split("_")[0] for t in textures}, {"medal", "credit"})
        build.ICON_TABLE = table
        with tempfile.TemporaryDirectory() as tmp:
            path = build.write_module(tmp, build.RESOURCE, build.built_source(), textures=textures)
            with open(path, "rb") as f:
                data = f.read()
            gpu = os.path.getsize(path + ".gpu_resources")
        magic, types, count = struct.unpack_from("<3I", data, 0)
        self.assertEqual((magic, types, count), (0xF0000011, 2, 17))
        self.assertGreaterEqual(gpu, sum(t[1] * t[2] * 4 for t in textures))
        at = data.index(b"-- HD2-Addon: mods/codex/medal_credit_markers\n")
        self.assertIn(b"\n-- HD2-Keep-On-Crash: yes", data[at:at + 400])

    def test_it_compiles_on_lua51(self):
        build.ICON_TABLE = TEST_ICONS
        lua = lua51.LuaRuntime()
        compiled = lua.eval("function(src) local f, err = loadstring(src, 'mod'); return f ~= nil, err end")
        ok, err = compiled(build.built_source())
        self.assertTrue(ok, err)


if __name__ == "__main__":
    unittest.main()
