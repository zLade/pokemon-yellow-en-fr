local out = io.open("tools/fceux_lua_smoke.ok", "w")
out:write("lua started\n")
out:close()

for i = 1, 5 do
  emu.frameadvance()
end

local out2 = io.open("tools/fceux_lua_smoke.ok", "a")
out2:write("lua finished\n")
out2:close()

os.exit()
