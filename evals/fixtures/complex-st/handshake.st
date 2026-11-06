FUNCTION_BLOCK FB_RequestProducer
VAR_INPUT
    NewRequest : BOOL;
    Ack : BOOL;
END_VAR
VAR_OUTPUT
    Request : BOOL;
END_VAR

IF Ack THEN
    Request := FALSE;
ELSIF NewRequest THEN
    Request := TRUE;
END_IF;
END_FUNCTION_BLOCK

FUNCTION_BLOCK FB_RequestConsumer
VAR_INPUT
    Request : BOOL;
    Permit : BOOL;
END_VAR
VAR_OUTPUT
    Busy : BOOL;
    Ack : BOOL;
END_VAR

Ack := FALSE;
IF Request AND Permit THEN
    Busy := TRUE;
END_IF;
IF Request AND NOT Request THEN
    Busy := FALSE;
    Ack := TRUE;
END_IF;
END_FUNCTION_BLOCK
