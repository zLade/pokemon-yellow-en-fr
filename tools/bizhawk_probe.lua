local out_path = "tools/bizhawk_probe.txt"
local out = io.open(out_path, "w")

local function log(s)
  out:write(tostring(s) .. "\n")
  out:flush()
end

log("bizhawk lua started")
log("emu.framecount=" .. tostring(emu.framecount()))

local ok, domains = pcall(memory.getmemorydomainlist)
if ok then
  log("domains:")
  for _, name in ipairs(domains) do
    local size = "?"
    pcall(function()
      memory.usememorydomain(name)
      size = tostring(memory.getmemorydomainsize(name))
    end)
    log("  " .. tostring(name) .. " size=" .. size)
  end
else
  log("memory.getmemorydomainlist failed: " .. tostring(domains))
end

for i = 1, 180 do
  emu.frameadvance()
end

log("after frames=" .. tostring(emu.framecount()))

pcall(function()
  client.screenshot("tools/bizhawk_probe.png")
  log("screenshot ok")
end)

out:close()

pcall(function() client.exit() end)
pcall(function() emu.exit() end)
