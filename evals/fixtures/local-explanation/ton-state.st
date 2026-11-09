tonStable(IN := xRequest AND xPermit, PT := T#200MS);
IF xFault THEN
    xRun := FALSE;
ELSIF tonStable.Q AND xPermit THEN
    xRun := TRUE;
END_IF;
xReady := xPermit AND NOT xFault;
