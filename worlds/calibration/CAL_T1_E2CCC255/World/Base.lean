namespace P3.CAL_T1_E2CCC255

universe u

inductive Q_direra {α : Type u} (R : α → α → Prop) : α → α → Type u where
  | q_dibuce (x : α) : Q_direra R x x
  | q_vucofi {x y z : α} : R x y → Q_direra R y z → Q_direra R x z

def q_tiwiza {α : Type u} (R : α → α → Prop) (P : α → Prop) : Prop :=
  ∀ (x y : α), R x y → P x → P y

end P3.CAL_T1_E2CCC255
