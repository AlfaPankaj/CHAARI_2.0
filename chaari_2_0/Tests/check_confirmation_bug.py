
import sys
import os

# Add current dir to path
sys.path.append(os.getcwd())

from core.confirmation import ConfirmationEngine, ConfirmationResult

def check_active_verify():
    print("=== Testing ConfirmationEngine active verify method ===")
    engine = ConfirmationEngine()
    
    # Request a code
    token = engine.generate("delete_file")
    digits = token.split('-')[1]
    
    # 1. Test verify with 1 argument (the old one used to have 1, the new one has 2 positional)
    print("\nCalling engine.verify(digits)...")
    try:
        # In Python, if we call verify(digits), it will try to match the last defined verify.
        # The last defined is: verify(self, token: str, submitted_code: str, session_id: str = "__default__")
        # So verify(digits) will FAIL if it's the last one (missing 1 required positional argument 'submitted_code')
        res = engine.verify(digits)
        print(f"Result of verify(digits): {res} (Type: {type(res)})")
    except TypeError as e:
        print(f"engine.verify(digits) FAILED as expected for the new signature: {e}")

    # 2. Test verify with 2 arguments
    print("\nCalling engine.verify(token, digits)...")
    try:
        res = engine.verify(token, digits)
        print(f"Result of verify(token, digits): {res}")
        print(f"Type of result: {type(res)}")
    except Exception as e:
        print(f"engine.verify(token, digits) FAILED: {e}")

    # 3. Test verify_pending
    print("\nCalling verify_pending(digits)...")
    res = engine.verify_pending(digits)
    print(f"Result of verify_pending(digits): {res} (Type: {type(res)})")

if __name__ == "__main__":
    check_active_verify()
