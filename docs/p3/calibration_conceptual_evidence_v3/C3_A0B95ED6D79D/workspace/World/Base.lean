import Std

namespace P3.CAL3_I_E87C49876088749B

structure State where
  x : Int
  y : Int
  z : Int
deriving DecidableEq, Repr

def move1 (s : State) : State := ⟨s.x + 2 * s.y + s.z - 2 * (1) - (-4), s.y + s.z - (-4), s.z⟩
def move2 (s : State) : State := ⟨s.x - 2 * s.y + s.z + 2 * (1) - (-4), s.y - s.z + (-4), s.z⟩
def move3 (s : State) : State := ⟨s.x, s.x + s.y - (-2), s.x + 2 * s.y + s.z - (-2) - 2 * (1)⟩
def move4 (s : State) : State := ⟨s.x, s.y - s.x + (-2), s.x - 2 * s.y + s.z - (-2) + 2 * (1)⟩

inductive Step : State → State → Prop where
  | first (s) : Step s (move1 s)
  | second (s) : Step s (move2 s)
  | third (s) : Step s (move3 s)
  | fourth (s) : Step s (move4 s)

inductive Reaches : State → State → Prop where
  | refl (s) : Reaches s s
  | tail {s t u} : Reaches s t → Step t u → Reaches s u

def start : State := ⟨20, 4, -3⟩

end P3.CAL3_I_E87C49876088749B
