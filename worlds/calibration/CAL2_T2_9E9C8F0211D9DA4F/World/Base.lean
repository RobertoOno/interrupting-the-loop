namespace P3.CAL2_T2_9E9C8F0211D9DA4F
universe u v

inductive ScopedIndex : Nat → Type where
  | first {n : Nat} : ScopedIndex (Nat.succ n)
  | rest {n : Nat} : ScopedIndex n → ScopedIndex (Nat.succ n)

inductive Q_tivugo (α : Type u) : Nat → Type u where
  | q_zofije {n : Nat} : ScopedIndex n → Q_tivugo α n
  | q_laduko {n : Nat} : α → Q_tivugo α n
  | q_karaka {n : Nat} : Q_tivugo α n → Q_tivugo α n → Q_tivugo α n
  | q_xiviyo {n : Nat} : Q_tivugo α n → Q_tivugo α (Nat.succ n) → Q_tivugo α n

def q_wemiyu {α : Type u} {n : Nat} (head : α) (tail : ScopedIndex n → α) : ScopedIndex (Nat.succ n) → α
  | .first => head
  | .rest i => tail i

def q_meduxi {α : Type u} {β : Type v} (f : α → β) {n : Nat} : Q_tivugo α n → Q_tivugo β n
  | .q_zofije i => .q_zofije i
  | .q_laduko a => .q_laduko (f a)
  | .q_karaka left right => .q_karaka (q_meduxi f left) (q_meduxi f right)
  | .q_xiviyo value body => .q_xiviyo (q_meduxi f value) (q_meduxi f body)

def q_yomuja {α : Type u} (op : α → α → α) {n : Nat}
    (env : ScopedIndex n → α) : Q_tivugo α n → α
  | .q_zofije i => env i
  | .q_laduko a => a
  | .q_karaka left right => op (q_yomuja op env left) (q_yomuja op env right)
  | .q_xiviyo value body => q_yomuja op (q_wemiyu (q_yomuja op env value) env) body

def q_qijogi {α : Type u} {β : Type v}
    (encode : α → β) (opA : α → α → α) (opB : β → β → β) : Prop :=
  ∀ x y, encode (opA x y) = opB (encode x) (encode y)

end P3.CAL2_T2_9E9C8F0211D9DA4F
