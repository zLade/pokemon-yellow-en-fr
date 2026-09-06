-- Controller queue with a mandatory neutral frame after every action.
--
-- Call tick() from Mesen's inputPolled callback.  clear()/abort() immediately
-- sends a neutral controller state, including when a state recovery interrupts
-- an in-progress hold.

local InputQueue = {}
InputQueue.__index = InputQueue

local BUTTONS = {
    "a",
    "b",
    "select",
    "start",
    "up",
    "down",
    "left",
    "right",
}

local VALID_BUTTON = {}
for _, button in ipairs(BUTTONS) do
    VALID_BUTTON[button] = true
end

local function requirePositiveInteger(value, label)
    if type(value) ~= "number"
        or value < 1
        or value ~= math.floor(value)
    then
        error(label .. " must be a positive integer", 3)
    end
end

local function neutralInput()
    local state = {}
    for _, button in ipairs(BUTTONS) do
        state[button] = false
    end
    return state
end

local function copyInput(source)
    local copy = neutralInput()
    for _, button in ipairs(BUTTONS) do
        copy[button] = source[button] == true
    end
    return copy
end

local function normalizeButtons(buttons)
    if type(buttons) == "string" then
        buttons = {buttons}
    end
    if type(buttons) ~= "table" then
        error("buttons must be a button name or table", 3)
    end

    local state = neutralInput()
    local count = 0
    for key, value in pairs(buttons) do
        local button
        if type(key) == "number" then
            button = value
        elseif value == true then
            button = key
        end
        if button ~= nil then
            if not VALID_BUTTON[button] then
                error("unknown controller button: " .. tostring(button), 3)
            end
            if not state[button] then
                state[button] = true
                count = count + 1
            end
        end
    end
    if count == 0 then
        error("an action must press at least one button", 3)
    end
    return state
end

function InputQueue.new(setInput, controller)
    if type(setInput) ~= "function" then
        error("setInput must be a function", 2)
    end
    return setmetatable({
        _set_input = setInput,
        _controller = controller or 0,
        _pending = {},
        _current = nil,
        _last = neutralInput(),
    }, InputQueue)
end

function InputQueue:_apply(state)
    self._last = copyInput(state)
    self._set_input(copyInput(state), self._controller)
end

function InputQueue:enqueue(buttons, holdFrames, releaseFrames, label)
    requirePositiveInteger(holdFrames, "holdFrames")
    if releaseFrames == nil then
        releaseFrames = 1
    end
    requirePositiveInteger(releaseFrames, "releaseFrames")

    self._pending[#self._pending + 1] = {
        input = normalizeButtons(buttons),
        hold_frames = holdFrames,
        release_frames = releaseFrames,
        label = label,
    }
    return self
end

function InputQueue:pulse(button, holdFrames, releaseFrames, label)
    return self:enqueue(
        button,
        holdFrames or 1,
        releaseFrames or 1,
        label
    )
end

function InputQueue:_take_next()
    if self._current ~= nil or #self._pending == 0 then
        return
    end
    self._current = table.remove(self._pending, 1)
    self._current.phase = "hold"
    self._current.remaining = self._current.hold_frames
end

function InputQueue:tick()
    self:_take_next()
    if self._current == nil then
        self:_apply(neutralInput())
        return false
    end

    if self._current.phase == "hold" then
        self:_apply(self._current.input)
        self._current.remaining = self._current.remaining - 1
        if self._current.remaining == 0 then
            self._current.phase = "release"
            self._current.remaining = self._current.release_frames
        end
        return true
    end

    -- A release phase is never skipped or combined with the next press.
    self:_apply(neutralInput())
    self._current.remaining = self._current.remaining - 1
    if self._current.remaining == 0 then
        self._current = nil
    end
    return true
end

function InputQueue:clear()
    self._pending = {}
    self._current = nil
    self:_apply(neutralInput())
end

function InputQueue:abort()
    self:clear()
end

function InputQueue:is_idle()
    if self._current ~= nil or #self._pending ~= 0 then
        return false
    end
    for _, button in ipairs(BUTTONS) do
        if self._last[button] then
            return false
        end
    end
    return true
end

function InputQueue:pending_count()
    return #self._pending + (self._current and 1 or 0)
end

function InputQueue:last_input()
    return copyInput(self._last)
end

return InputQueue
