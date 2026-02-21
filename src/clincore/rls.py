from __future__ import annotations

from typing import Optional
from fastapi import Header, HTTPException

def get_tenant_id_header(x_tenant_id: Optional[str] = Header(default=None)) -> Optional[str]:
    # در فاز v0.1 برای fail-closed بودن اگر APIهایی tenant-based باشند باید tenant بدهند.
    # اما برای بعضی endpointها مثل health میتونه None باشه.
    if x_tenant_id is None:
        return None
    x_tenant_id = x_tenant_id.strip()
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-Id is empty")
    return x_tenant_id
