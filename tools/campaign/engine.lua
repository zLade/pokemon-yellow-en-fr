-- Small deterministic state-machine used by the Mesen campaign harness.
--
-- A state is deliberately explicit: it must provide entry, success, timeout
-- and recovery.  This prevents a route step from silently waiting forever.

local Engine = {}
Engine.__index = Engine

local function requireFunction(value, label)
    if type(value) ~= "function" then
        error(label .. " must be a function", 3)
    end
end

local function requireNonNegativeInteger(value, label)
    if type(value) ~= "number"
        or value < 0
        or value ~= math.floor(value)
    then
        error(label .. " must be a non-negative integer", 3)
    end
end

local function shallowCopy(source)
    local copy = {}
    for key, value in pairs(source) do
        copy[key] = value
    end
    return copy
end

function Engine.new(options)
    options = options or {}
    requireFunction(options.now, "options.now")
    if options.log ~= nil then
        requireFunction(options.log, "options.log")
    end

    return setmetatable({
        _now = options.now,
        _log = options.log,
        _states = {},
        _journal = {},
        _status = "idle",
        _context = nil,
        _run = nil,
        _result = nil,
        _last_error = nil,
    }, Engine)
end

function Engine:add_state(name, specification)
    if type(name) ~= "string" or name == "" then
        error("state name must be a non-empty string", 2)
    end
    if self._states[name] ~= nil then
        error("duplicate state: " .. name, 2)
    end
    if type(specification) ~= "table" then
        error("state specification must be a table", 2)
    end

    requireFunction(specification.entry, name .. ".entry")
    requireFunction(specification.success, name .. ".success")
    requireNonNegativeInteger(specification.timeout, name .. ".timeout")
    requireFunction(specification.recovery, name .. ".recovery")

    local maxRecoveries = specification.max_recoveries
    if maxRecoveries == nil then
        maxRecoveries = 1
    end
    requireNonNegativeInteger(
        maxRecoveries,
        name .. ".max_recoveries"
    )
    if specification.next ~= nil
        and type(specification.next) ~= "string"
        and type(specification.next) ~= "function"
    then
        error(name .. ".next must be a state name or function", 2)
    end

    local stored = shallowCopy(specification)
    stored.max_recoveries = maxRecoveries
    self._states[name] = stored
    return self
end

function Engine:_record(kind, details)
    local row = {
        frame = self._now(),
        kind = kind,
        state = self._run and self._run.name or nil,
    }
    if details ~= nil then
        for key, value in pairs(details) do
            row[key] = value
        end
    end
    self._journal[#self._journal + 1] = row
    if self._log ~= nil then
        self._log(row)
    end
end

function Engine:_enter_state(name)
    if self._states[name] == nil then
        error("unknown state: " .. tostring(name), 2)
    end
    self._run = {
        name = name,
        entered = false,
        entered_at = nil,
        recoveries = 0,
    }
    self:_record("transition", {target = name})
end

function Engine:start(initialState, context)
    if self._status == "running" then
        error("campaign engine is already running", 2)
    end
    if self._states[initialState] == nil then
        error("unknown initial state: " .. tostring(initialState), 2)
    end

    self._journal = {}
    self._status = "running"
    self._context = context or {}
    self._result = nil
    self._last_error = nil
    self._run = nil
    self:_record("start", {target = initialState})
    self:_enter_state(initialState)
    return self
end

function Engine:_fail(reason, message)
    self._status = "failed"
    self._last_error = {
        reason = reason,
        message = tostring(message or reason),
        state = self._run and self._run.name or nil,
        frame = self._now(),
    }
    self:_record("failed", self._last_error)
    return self._status
end

local function normalizeRecovery(decision)
    if decision == nil or decision == true or decision == "retry" then
        return "retry", nil
    end
    if decision == false or decision == "fail" then
        return "fail", nil
    end
    if type(decision) == "string" then
        return "transition", decision
    end
    if type(decision) == "table" then
        local action = decision.action or "retry"
        if action == "transition" then
            return action, decision.state
        end
        return action, decision.message
    end
    return "fail", "invalid recovery decision"
end

function Engine:_recover(reason, message)
    local run = self._run
    local specification = self._states[run.name]
    run.recoveries = run.recoveries + 1

    if run.recoveries > specification.max_recoveries then
        return self:_fail(
            reason,
            "recovery budget exhausted: " .. tostring(message or reason)
        )
    end

    local details = {
        reason = reason,
        message = tostring(message or reason),
        attempt = run.recoveries,
        entered_at = run.entered_at,
    }
    self:_record("recovery", details)
    local ok, decision = pcall(
        specification.recovery,
        self._context,
        shallowCopy(details)
    )
    if not ok then
        return self:_fail("recovery_error", decision)
    end

    local action, value = normalizeRecovery(decision)
    if action == "retry" then
        run.entered = false
        run.entered_at = nil
        self:_record("retry", {attempt = run.recoveries})
        return self._status
    end
    if action == "transition" then
        if type(value) ~= "string" or self._states[value] == nil then
            return self:_fail(
                "invalid_recovery_target",
                "unknown recovery state: " .. tostring(value)
            )
        end
        self:_enter_state(value)
        return self._status
    end
    return self:_fail(reason, value or message)
end

function Engine:_succeed(payload)
    local completedName = self._run.name
    local specification = self._states[completedName]
    self:_record("success", {payload = payload})

    local nextState = specification.next
    if type(nextState) == "function" then
        local ok, selected = pcall(
            nextState,
            self._context,
            payload,
            completedName
        )
        if not ok then
            return self:_recover("next_error", selected)
        end
        nextState = selected
    end

    if nextState == nil then
        self._status = "completed"
        self._result = payload
        self:_record("completed", {payload = payload})
        return self._status
    end
    if type(nextState) ~= "string" or self._states[nextState] == nil then
        return self:_fail(
            "invalid_next_state",
            "unknown next state: " .. tostring(nextState)
        )
    end
    self:_enter_state(nextState)
    return self._status
end

function Engine:tick()
    if self._status == "idle" then
        error("campaign engine has not been started", 2)
    end
    if self._status ~= "running" then
        return self._status
    end

    local run = self._run
    local specification = self._states[run.name]
    if not run.entered then
        run.entered = true
        run.entered_at = self._now()
        self:_record("entry", {attempt = run.recoveries + 1})
        local ok, entryError = pcall(
            specification.entry,
            self._context,
            run.recoveries + 1
        )
        if not ok then
            return self:_recover("entry_error", entryError)
        end
    end

    local ok, succeeded, payload = pcall(
        specification.success,
        self._context,
        self._now() - run.entered_at
    )
    if not ok then
        return self:_recover("success_error", succeeded)
    end
    if succeeded then
        return self:_succeed(payload)
    end

    local elapsed = self._now() - run.entered_at
    if elapsed >= specification.timeout then
        return self:_recover(
            "timeout",
            string.format(
                "state %s timed out after %d frames",
                run.name,
                elapsed
            )
        )
    end
    return self._status
end

function Engine:get_status()
    return self._status
end

function Engine:current_state()
    return self._run and self._run.name or nil
end

function Engine:get_result()
    return self._result
end

function Engine:get_last_error()
    return self._last_error and shallowCopy(self._last_error) or nil
end

function Engine:get_journal()
    local copy = {}
    for index, row in ipairs(self._journal) do
        copy[index] = shallowCopy(row)
    end
    return copy
end

return Engine
