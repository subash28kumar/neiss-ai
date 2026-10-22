"""InjuryCoder: circumstance flags read from NEISS injury narratives (added in v1.4).

NEISS does not code whether a motor vehicle was involved or whether the rider wore a helmet,
but the narrative often says so. These rules read the narrative text:

* ``motor_vehicle(text)`` -> True when the patient was hit by, crashed into, or struck part of
  a motor vehicle (moving or parked, including a car door), or the narrative calls it an MVC/MVA.
  Swerving to avoid a car without contact is not counted.
* ``helmet(text)`` -> "yes", "no" or "not mentioned". "Not mentioned" includes unclear wording
  such as "HELMET NS" and is never treated as "no".

Validation (held-out test of 300 random narratives, 2019-2025; see VALIDATION.md): motor vehicle
accuracy 98.3%, sensitivity 93.6%, precision 95.7%; helmet 300/300 correct.
"""
from __future__ import annotations

import re
MOD = r"(?:(?:A|AN|THE|HIS|HER|MOVING|PARKED|ONCOMING|PASSING|GARBAGE|DUMP|BOX|PICKUP|PICK-UP|DELIVERY|POLICE|SCHOOL|CITY|SEMI|TOW|FIRE|ANOTHER|SMALL|LARGE|BIG|WHITE|BLACK|RED|SLOW|SLOW-MOVING|REVERSING|BACKING|TURNING|STATIONARY|[A-Z]+'S|STOPPED|SPEEDING|DADS|MOMS|DAD'S|MOM'S|NEIGHBORS|NEIGHBOR'S|FRIENDS|FRIEND'S|PARKED)\s+){0,3}"
VEH = r"(?:MVS?|CARS?|TRUCKS?|VEHICLES?|SUVS?|VANS?|MINIVAN|BUS|BUSES|AUTOS?|AUTOMOBILES?|PICKUPS?|SEMIS?|TAXI|CAB|JEEP|SEDAN|MOTOR\s+VEHICLES?|MOTORCYCLES?|TRACTOR[- ]TRAILER|18[- ]WHEELER|UBER|LYFT)"
MV = re.compile("|".join([
    rf"\b(?:HIT|STRUCK|STRIKE[SD]?|STRIKING|HITTING|GRAZED|CLIPPED|SIDE\s*SWIPED|SIDESWIPED|BUMPED|KNOCKED\s+(?:DOWN|OVER|OFF)|RUN\s+OVER|RAN\s+OVER|REAR[- ]ENDED|T-?BONED|COLLID\w*\s+WITH|CRASH\w*\s+INTO)\s+(?:BY\s+)?(?:(?:THE|A)\s+)?(?:(?:SIDE|BACK|FRONT|REAR|HOOD|DOOR)\s+OF\s+)?{MOD}{VEH}\b",
    rf"(?:\bINTO|\bWITH|\bAGAINST|\bONTO|\bOVER|\bAT|\bW/)\s+(?:THE\s+|A\s+)?(?:BACK|SIDE|FRONT|HOOD|DOOR|REAR)?\s*(?:OF\s+)?{MOD}{VEH}\b(?!\s+(?:SEAT|PARK|LOT|WASH))",
    rf"\b{VEH}\s*(?:VS\.?|V\.?|VERSUS)\s",
    rf"\s(?:VS\.?|V\.?|VERSUS)\s+{MOD}{VEH}\b",
    rf"\b{VEH}\b[^.;]{{0,40}}\b(?:HIT|HITS|STRUCK|STRIKES|RAN\s+INTO|CRASHED\s+INTO|COLLIDED|PULLED\s+OUT|CUT\s+(?:HIM|HER|THEM)\s+OFF|RAN\s+(?:HIM|HER)\s+OVER|BACKED\s+INTO|TURNED\s+INTO|DOOR\s+OPENED|OPENED\s+(?:THE|A|ITS|HIS|HER)?\s*DOOR|SIDE\s*SWIPED|SIDESWIPED|CLIPP\w+|SWERVED\s+INTO|KNOCKED|RAN\s+OVER|REAR[- ]ENDED|T-?BONED|BACKED\s+(?:UP\s+)?INTO)",
    rf"\b{VEH}\b[^.;]{{0,60}}\b(?:CRASHED|RAN|SLAMMED|RODE|WENT|HIT)\s+(?:HEAD[- ]ON\s+)?(?:INTO\s+)?(?:IT|HIM|HER|THEM)\b",
    rf"(?<!CUT OFF )(?<!CUT HIM OFF )(?<!CUT HER OFF )(?<!AVOID )\bBY\s+{MOD}{VEH}\b",
    rf"\b(?:MIRROR|DOOR|TIRE|WHEEL|HOOD|BUMPER|PEDAL|FENDER|WINDSHIELD|TAILGATE|TRAILER)\s+OF\s+{MOD}{VEH}\b",
    rf"\b(?:HIT|STRUCK|BUMPED)\s+(?:HIS\s+|HER\s+)?(?:HEAD|FACE|ARM|LEG|KNEE|SHOULDER|HAND)\s+(?:ON|AGAINST)\s+{MOD}{VEH}\b",
    r"\b(?:MVC|MVA|MV\s*C|AUTO\s*(?:VS|PED)|AUTO-PED|PED(?:ESTRIAN)?\s+STRUCK(?!\s+BY\s+(?:A\s+|AN\s+)?(?:BICYCL\w*|BIKE\w*|E-?BIKE|SCOOTER|E-?SCOOTER|SKATEBOARD|MOPED|CYCLIST|BICYCLIST))|DOORED|CAR\s+DOOR|MOTOR\s+VEHICLE\s+(?:COLLISION|ACCIDENT|CRASH)|BIKE\s+VS\.?\s+(?:CAR|AUTO|TRUCK)|BICYCLE\s+VS\.?\s+(?:CAR|AUTO|TRUCK))\b",
]))
EARLIER = re.compile(r"\b(?:\d+\s+(?:DAYS?|WEEKS?|MONTHS?|YEARS?|YRS?|WKS?)\s+AGO|LAST\s+(?:WEEK|MONTH|YEAR))\b[^.]{0,60}\b(?:MVC|MVA|CAR\s+ACCIDENT)")

LOADING = re.compile(rf"\b(?:LIFT\w*|LOAD\w*|PUT\w*|PLAC\w*|PUSH\w*|PULL\w*|CARRY\w*|GETTING|GET)\b[^.;]{{0,30}}\b(?:INTO|ONTO|IN|OUT\s+OF|OFF)\s+(?:THE\s+|A\s+|HIS\s+|HER\s+)?{VEH}\b")

def _clean(text):
    t = (text or "").upper()
    return re.sub(r"(?<=[A-Z])DX\b", " DX", t)   # 'VEHICLEDX' -> 'VEHICLE DX'

def motor_vehicle(text):
    t = _clean(text)
    t = LOADING.sub(" ", t)   # loading a bike into a car is not a crash
    return bool(MV.search(t))

NO = re.compile("|".join([
    r"\bNO\s+(?:BIKE\s+|BICYCLE\s+)?HELMETS?(?=\b|DX)", r"\bUN-?HELM\w*", r"\bNO\s+WEARING\b", r"\bNON-?HELMETT?ED\b", r"\bU[A-Z]{1,2}HELMETT?ED\b", r"\bNOT\s+HELMETT?ED\b", r"\bREFUSED\s+TO\s+WEAR\s+(?:A\s+|HIS\s+|HER\s+)?HELMET", r"\bW/\s?O\s+(?:A\s+)?HELMET", r"\bNO\s+(?:HELMET\s+)?(?:AND|OR|/)\s*(?:NO\s+)?LOC\b",
    r"\bW/O\s+(?:A\s+|HIS\s+|HER\s+)?HELMET", r"\bWITHOUT\s+(?:A\s+|HIS\s+|HER\s+|WEARING\s+(?:A\s+)?)?HELMET",
    r"\bNOT\s+(?:WEARING|WEAR|USING|HAVE|HAVING)\s+(?:ON\s+)?(?:A\s+|HIS\s+|HER\s+|ANY\s+)?HELMET",
    r"\b(?:WAS|WERE)\s*N'?O?T\s+(?:WEARING|HELMETT?ED)", r"\bWASN'?T\s+(?:WEARING|HELMETT?ED)",
    r"\bDIDN'?T\s+(?:HAVE|WEAR)\s+(?:ON\s+)?(?:A\s+)?HELMET", r"\bDID\s+NOT\s+(?:HAVE|WEAR)\s+(?:ON\s+)?(?:A\s+)?HELMET",
    r"\bDENIES\s+(?:WEARING\s+)?(?:A\s+)?HELMET", r"(?<![A-Z0-9])-\s?HELMET", r"\bHELMET\s*[-:]\s*(?:NO|NEG|NONE|-)(?!\w)",
    r"\bHELMET\s*(?:-)(?!\w)", r"\bHELMET\s+(?:NOT|NEVER)\s+(?:WORN|USED|ON)", r"\bNEG(?:ATIVE)?\s+(?:FOR\s+)?HELMET",
    r"\bNO\s+(?:LOC\s*/\s*|LOC\s*,\s*|LOC\s+OR\s+|LOC\s+AND\s+)HELMET", r"\bNOR\s+HELMET",
]))
YES = re.compile("|".join([
    r"\+\s?HELMET", r"\bHELMETT?ED\b", r"\bHELMET\s*\+", r"\b(?:WEARING|WEARIN|WERARING|WORE|WEARS|WITH|HAD\s+ON|HAD|W/)\s*(?:ON\s+)?(?:A\s+|HIS\s+|HER\s+|THEIR\s+|FULL[- ]FACE\s+|FULL\s+|HALF\s+|BIKE\s+|BICYCLE\s+|SCOOTER\s+|PROPER\s+|DIRT\s*BIKE\s+)*HELMETS?(?=\b|DX)",
    r"\bHELMETS?\s+(?:ON|USE|USED|WORN|IN\s+PLACE|PRESENT|WAS\s+ON|INTACT|DAMAGED|BROKE|BROKEN|CRACKED|SPLIT)\b",
    r"\b(?:UNDER|THROUGH|CRACKED|CRACKING|BROKE|BREAKING|BROKEN|DAMAGED|DENTED|SPLIT|HIT|HITTING|STRIKING|STRUCK)\s+(?:HIS\s+|HER\s+|THE\s+|THEIR\s+)?HELMET",
    r"\bHELMET\s*[:=]\s*(?:YES|Y|POS|\+)(?!\w)", r"\+\s?[A-Z ]{0,25}(?:AND|&)\s+HELMET", r"\bHELMETT?(?:ED)?\s+(?:DRIVER|RIDER|BICYCLIST|CYCLIST|OPERATOR|BIKER)", r"\bHELMETS?\s+(?:WAS|IS|GOT|WERE)\s+(?:CRACKED|BROKEN|DAMAGED|SPLIT|DENTED|ON|WORN|SCRATCHED)", r"\bPOS(?:ITIVE)?\s+(?:FOR\s+)?HELMET",
]))
UNK = re.compile(r"(?:\bHELMET\s*(?:USE\s+)?(?:NS|N/S|UNK|UNKNOWN|NOT\s+(?:STATED|SPECIFIED|DOCUMENTED|REPORTED|NOTED|KNOWN))|UNKNOWN\s+(?:IF\s+|WHETHER\s+)?(?:\w+\s+)?HELMET|UNK\s+(?:IF\s+)?HELMET|\?\s*HELMET|HELMET\s*\?|HELMET\s+USE\s+UNK)")

def helmet(text):
    t = _clean(text)
    if "HELMET" not in t:
        return "not mentioned"
    if UNK.search(t):
        return "not mentioned"
    no = bool(NO.search(t))
    yes = bool(YES.search(NO.sub(" ", t)))
    if no and not yes: return "no"
    if yes and not no: return "yes"
    return "not mentioned"
