namespace P3.CAL_T2_15CCB41E

universe u v

inductive Q_jabika (α : Type u) where
  | q_cobize : α → Q_jabika α
  | q_dituca : Q_jabika α → Q_jabika α → Q_jabika α

def q_docecu {α : Type u} {β : Type v} (f : α → β) : Q_jabika α → Q_jabika β
  | .q_cobize x => .q_cobize (f x)
  | .q_dituca left right => .q_dituca (q_docecu f left) (q_docecu f right)

def q_zawasi {α : Type u} (op : α → α → α) : Q_jabika α → α
  | .q_cobize x => x
  | .q_dituca left right => op (q_zawasi op left) (q_zawasi op right)

def q_dowole {α : Type u} {β : Type v}
    (encode : α → β) (opA : α → α → α) (opB : β → β → β) : Prop :=
  ∀ (x y : α), encode (opA x y) = opB (encode x) (encode y)

end P3.CAL_T2_15CCB41E
