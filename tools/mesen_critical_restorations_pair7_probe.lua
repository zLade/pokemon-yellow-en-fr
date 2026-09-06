-- Assisted renderer proof for the four miswired pair-7 restorations.
--
-- The normal controller-only campaign route is retained, while four early
-- laboratory dialogue pointers are temporarily redirected to the final four
-- distinct Nugget Bridge reply payloads.  All pointers are restored at the
-- campaign finalize hook before the scenario can pass.

local outputDirectory = os.getenv("POKEMON_YELLOW_MESEN_OUTPUT")
if outputDirectory == nil or outputDirectory == "" then
    error("POKEMON_YELLOW_MESEN_OUTPUT is not set")
end

local function scriptDirectory()
    local source = debug.getinfo(1, "S").source or ""
    if source:sub(1, 1) == "@" then
        source = source:sub(2)
    end
    local directory = source:match("^(.*)[/\\][^/\\]+$")
    if directory == nil or directory == "" then
        error("cannot determine script directory")
    end
    return directory
end

local directory = scriptDirectory()
local separator = directory:find("\\", 1, true) and "\\" or "/"
local Runtime = dofile(
    directory .. separator .. "critical_restoration_runtime.lua"
)
local runtime = Runtime.new({group = "pair7", expectedCount = 4})
runtime:install()

local function writeBinary(filename, data)
    local file = assert(io.open(outputDirectory .. "\\" .. filename, "wb"))
    file:write(data)
    file:close()
end

POKEMON_CAMPAIGN_FINALIZE_HOOK = function(status, endpoint, frame)
    local allRead = runtime:allRead()
    local restored = runtime:restore()
    local pass = status == "completed" and
        endpoint == "outside_lab_stable" and
        allRead and restored
    writeBinary(
        pass
            and "critical_restorations_pair7_final_screen.png"
            or "critical_restorations_pair7_failure_screen.png",
        emu.takeScreenshot()
    )
    runtime:writeReport(
        "critical_restorations_pair7_validation.txt",
        {
            "campaign_status=" .. tostring(status),
            "campaign_endpoint=" .. tostring(endpoint),
            "frames=" .. tostring(frame),
            "all_payloads_read=" .. tostring(allRead),
            "result=" .. (pass and "PASS" or "FAIL"),
        }
    )
    if not pass then
        error(
            "pair7 restoration proof failed: status=" .. tostring(status) ..
            " endpoint=" .. tostring(endpoint) ..
            " allRead=" .. tostring(allRead) ..
            " restored=" .. tostring(restored)
        )
    end
    print(string.format(
        "POKEMON_CRITICAL_RESTORATIONS_PAIR7_PASS mapper=163 region=%s " ..
        "frames=%d payloads=4 mode=assisted_transient_prg_pointer_patch " ..
        "restored=true",
        tostring(emu.getState()["region"]),
        frame
    ))
end

dofile(
    directory .. separator .. "campaign" .. separator ..
    "mesen_campaign_prototype.lua"
)
