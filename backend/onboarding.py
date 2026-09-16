"""Versioned product tour, stored in the existing tenant-protected settings table."""
from typing import Literal
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from .db import Setting, get_setting, now

TOUR_VERSION = 1
STEPS = ('quick-entry', 'journal', 'import', 'analytics', 'calendar', 'coach', 'accounts', 'wallet')
KEY = 'onboarding'


class TourAction(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    version: Literal[1]
    revision: int = Field(ge=0)
    action: Literal['next', 'back', 'skip', 'complete', 'restart']


def initial_state(status='pending'):
    return {'version': TOUR_VERSION, 'status': status, 'step': STEPS[0], 'revision': 0,
            'started_at': None, 'finished_at': None}


def initialize(db):
    """Called under the profile lock, only when provisioning the first workspace."""
    if not get_setting(db, KEY):
        db.add(Setting(key=KEY, value=initial_state()))


def state(db):
    record = get_setting(db, KEY)
    # Accounts with a workspace predating the tour are opt-in. Do not surprise them.
    return dict(record.value) if record else initial_state('not_required')


def transition(db, payload: TourAction):
    from .entitlements import lock_user
    lock_user(db)
    current = state(db)
    if current['version'] != payload.version or current['revision'] != payload.revision:
        raise HTTPException(409, {'code': 'onboarding_conflict',
                                 'message': 'Your tour changed in another tab. Loading the latest step.'})
    action = payload.action
    if action != 'restart' and current['status'] not in ('pending', 'in_progress'):
        raise HTTPException(409, {'code': 'onboarding_conflict', 'message': 'This tour has already ended.'})
    index = STEPS.index(current['step'])
    updated = {**current, 'revision': current['revision'] + 1,
               'status': 'in_progress', 'started_at': current['started_at'] or now()}
    if action == 'restart':
        updated.update(step=STEPS[0], started_at=now(), finished_at=None)
    elif action == 'next' and index < len(STEPS) - 1:
        updated['step'] = STEPS[index + 1]
    elif action == 'back' and index > 0:
        updated['step'] = STEPS[index - 1]
    elif action == 'skip' or (action == 'complete' and index == len(STEPS) - 1):
        updated.update(status='skipped' if action == 'skip' else 'completed', finished_at=now())
    else:
        raise HTTPException(422, 'This action is not available at the current tour step.')
    record = get_setting(db, KEY)
    if record:
        record.value = updated
    else:
        db.add(Setting(key=KEY, value=updated))
    db.flush()
    return updated
