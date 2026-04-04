import casbin
import os
from app.core.config import settings

def get_enforcer():
    # paths to the model and policy files
    model_path = os.path.join(os.path.dirname(__file__), "rbac_model.conf")
    policy_path = os.path.join(os.path.dirname(__file__), "policy.csv")
    
    # initialize the enforcer with the file adapter
    e = casbin.Enforcer(model_path, policy_path)
    return e

# create a singleton instance
enforcer = get_enforcer()
