# Worked example

A separate formal problem and its complete proof.

```lean
import Std

namespace Source

structure State where
  u : Int
  v : Int
  w : Int
deriving DecidableEq, Repr

def move1 (s : State) : State := ⟨s.u, s.v + 2 * s.w + s.u, s.w + s.u⟩
def move2 (s : State) : State := ⟨s.u, s.v - 2 * s.w + s.u, s.w - s.u⟩
def move3 (s : State) : State := ⟨s.u + 2 * s.w + s.v, s.v, s.w + s.v⟩
def move4 (s : State) : State := ⟨s.u - 2 * s.w + s.v, s.v, s.w - s.v⟩

inductive Step : State → State → Prop where
  | first (s) : Step s (move1 s)
  | second (s) : Step s (move2 s)
  | third (s) : Step s (move3 s)
  | fourth (s) : Step s (move4 s)

inductive Reaches : State → State → Prop where
  | refl (s) : Reaches s s
  | tail {s t u} : Reaches s t → Step t u → Reaches s u

def start : State := ⟨1, 5, 2⟩

def measure (s : State) : Int := s.v * s.u - s.w * s.w

theorem step_measure {s t : State} (h : Step s t) : measure s = measure t := by
  cases h <;> simp only [measure, move1, move2, move3, move4] <;> grind

theorem bridge {s t : State} (h : Reaches s t) : measure s = measure t := by
  induction h with
  | refl => rfl
  | tail _ step ih => exact ih.trans (step_measure step)

theorem source_solution : ∀ b c : Int, ¬ Reaches start ⟨c, 0, b⟩ := by
  intro b c h
  have conserved := bridge h
  have nonnegative := Int.sq_nonneg b
  grind [measure, start]

end Source
```
