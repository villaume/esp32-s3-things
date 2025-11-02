#import esp
#esp.osdebug(None)
#import webrepl
#webrepl.start()

import time

# Wait a moment for system to stabilize
time.sleep(2)

# Run main program
try:
    import main
except Exception as e:
    print(f"Error starting main: {e}")