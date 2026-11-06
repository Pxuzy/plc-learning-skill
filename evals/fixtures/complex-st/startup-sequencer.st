FUNCTION_BLOCK FB_StartupSequencer
VAR_INPUT
    Start : BOOL;
    Hold : BOOL;
    Reset : BOOL;
    InterlocksOK : BOOL;
    Feedback : BOOL;
    ElapsedMs : DINT;
    TimeoutMs : DINT;
END_VAR
VAR_OUTPUT
    RunCommand : BOOL;
    Fault : BOOL;
    State : INT;
END_VAR
VAR
    StartAttempts : UINT;
END_VAR

RunCommand := FALSE;

IF Reset AND (State = 90) THEN
    State := 0;
    Fault := FALSE;
    StartAttempts := 0;
END_IF;

CASE State OF
    0:
        Fault := FALSE;
        IF Start AND InterlocksOK THEN
            State := 10;
            StartAttempts := StartAttempts + 1;
        END_IF;
    10:
        IF NOT InterlocksOK THEN
            State := 90;
            Fault := TRUE;
        ELSIF Feedback THEN
            State := 20;
        ELSIF ElapsedMs >= TimeoutMs THEN
            State := 90;
            Fault := TRUE;
        ELSE
            RunCommand := TRUE;
        END_IF;
    20:
        IF NOT InterlocksOK THEN
            State := 90;
            Fault := TRUE;
        ELSIF Hold THEN
            State := 30;
        ELSE
            RunCommand := TRUE;
        END_IF;
    30:
        IF NOT InterlocksOK THEN
            State := 90;
            Fault := TRUE;
        ELSIF NOT Hold THEN
            State := 20;
        END_IF;
    90:
        Fault := TRUE;
END_CASE;
END_FUNCTION_BLOCK
