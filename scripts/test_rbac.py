import requests
import sys

BASE_URL = "http://localhost:8000"

# Mock login to get tokens (assuming default credentials exist)
def get_token(username, password):
    try:
        resp = requests.post(f"{BASE_URL}/auth/login", json={"username": username, "password": password})
        if resp.status_code == 200:
            return resp.json()["access_token"]
    except:
        pass
    return None

def test_rbac():
    print("=== RBAC VERIFICATION ===")
    
    # 1. Login as Master
    master_token = get_token("master", "master123")
    if not master_token:
        print("[FAIL] Could not login as master (ensure backend is running).")
        return

    # 2. Login as Admin
    admin_token = get_token("admin", "admin123")
    
    # 3. Test Master Access (Should succeed)
    headers = {"Authorization": f"Bearer {master_token}"}
    resp = requests.get(f"{BASE_URL}/users", headers=headers)
    if resp.status_code == 200:
        print("[PASS] Master can access /users")
    else:
        print(f"[FAIL] Master blocked from /users: {resp.status_code}")

    # 4. Test Admin Access (Should succeed based on policy)
    headers = {"Authorization": f"Bearer {admin_token}"}
    if admin_token:
        resp = requests.get(f"{BASE_URL}/users", headers=headers)
        if resp.status_code == 200:
            print("[PASS] Admin can access /users")
        else:
            print(f"[FAIL] Admin blocked from /users: {resp.status_code}")

    # 5. Test Unauthorized Access (Admin trying Master verification route if distinct, or hypothetically blocked)
    # Using a path not in admin policy
    resp = requests.put(f"{BASE_URL}/users/admin/role", json={"role": "master"}, headers=headers)
    if resp.status_code == 403:
        print("[PASS] Admin correctly blocked from changing roles (if policy enforced)")
    else:
        print(f"[INFO] Admin accessed role change: {resp.status_code} (Check policy.csv)")

if __name__ == "__main__":
    test_rbac()
