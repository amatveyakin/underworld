# partial Game class

class Cell:
    def __init__(self):
        self.moveCandidates = []
        
class Object(Cell):
    TakesDamage = True
    VisionRange = 3
    CanBeBuilt = True
    def __init__(self):
        super().__init__()
        if self.TakesDamage:
            self.hitpoints = self.MaxHitpoints
        self.newPosition = None
        self.willMove = None
        self.hasSpawnRequest = False

class Building (Object):
    CanMove = False
    CanAttack = False

class Castle (Building):
    MaxHitpoints = 10000
    CanBeBuilt = False
    CharRepr  = "C"

class Farm (Building):
    MaxHitpoints = 1000
    Cost = 1000
    CharRepr  = "F"

class Barracks (Building):
    MaxHitpoints = 1500
    Cost = 1500
    CharRepr = "B"

class Unit (Object):
    CanMove = True
    CanAttack = True

class Warrior (Unit):
    MaxHitpoints = 500
    DamageToBuilding = 100
    DamageToUnits = 100
    Cost = 500
    CharRepr = "W"
    AttackRange = 2

class Wall(Building):
    TakesDamage = False
    CanBeBuilt = False
    CanAttack = False
    CanMove = False
    def __init__(self):
        super().__init__( )
        self.owner = -1
    CharRepr = "#"

ObjTypes = [Castle, Farm, Barracks, Warrior, Wall]
ObjTypeDict = {objType.CharRepr : objType for objType in ObjTypes}
