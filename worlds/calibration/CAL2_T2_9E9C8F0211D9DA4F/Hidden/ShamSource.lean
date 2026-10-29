namespace S_zeluto
universe u v

inductive ScopedIndex : Nat → Type where
  | first {n : Nat} : ScopedIndex (Nat.succ n)
  | rest {n : Nat} : ScopedIndex n → ScopedIndex (Nat.succ n)

inductive Q_vokipa (α : Type u) : Nat → Type u where
  | q_mogude {n : Nat} : ScopedIndex n → Q_vokipa α n
  | q_cisopo {n : Nat} : α → Q_vokipa α n
  | q_biyeha {n : Nat} : Q_vokipa α n → Q_vokipa α n → Q_vokipa α n
  | q_xunawu {n : Nat} : Q_vokipa α n → Q_vokipa α (Nat.succ n) → Q_vokipa α n

def q_yocije {α : Type u} {n : Nat} (head : α) (tail : ScopedIndex n → α) : ScopedIndex (Nat.succ n) → α
  | .first => head
  | .rest i => tail i

def q_kuwaqi {α : Type u} {β : Type v} (f : α → β) {n : Nat} : Q_vokipa α n → Q_vokipa β n
  | .q_mogude i => .q_mogude i
  | .q_cisopo a => .q_cisopo (f a)
  | .q_biyeha left right => .q_biyeha (q_kuwaqi f right) (q_kuwaqi f left)
  | .q_xunawu value body => .q_xunawu (q_kuwaqi f value) (q_kuwaqi f body)

def q_tegiso {α : Type u} (op : α → α → α) {n : Nat}
    (env : ScopedIndex n → α) : Q_vokipa α n → α
  | .q_mogude i => env i
  | .q_cisopo a => a
  | .q_biyeha left right => op (q_tegiso op env left) (q_tegiso op env right)
  | .q_xunawu value body => q_tegiso op (q_yocije (q_tegiso op env value) env) body

def q_wujuma {α : Type u} {β : Type v}
    (encode : α → β) (opA : α → α → α) (opB : β → β → β) : Prop :=
  ∀ x y, encode (opA x y) = opB (encode y) (encode x)

end S_zeluto
namespace S_zeluto
universe u v

theorem solved_bridge {α : Type u} {β : Type v}
    (encode : α → β) (opA : α → α → α) (opB : β → β → β)
    (h : q_wujuma encode opA opB) {n : Nat} (t : Q_vokipa α n) :
    ∀ (envA : ScopedIndex n → α) (envB : ScopedIndex n → β),
      (∀ i, encode (envA i) = envB i) →
      encode (q_tegiso opA envA t) = q_tegiso opB envB (q_kuwaqi encode t) := by
  induction t with
  | q_mogude i =>
      intro envA envB related
      exact related i
  | q_cisopo a =>
      intro envA envB related
      rfl
  | q_biyeha left right ihLeft ihRight =>
      intro envA envB related
      simp only [q_tegiso, q_kuwaqi]
      rw [h, ihRight envA envB related, ihLeft envA envB related]
  | q_xunawu value body ihValue ihBody =>
      intro envA envB related
      simp only [q_tegiso, q_kuwaqi]
      apply ihBody
      intro i
      cases i with
      | first => exact ihValue envA envB related
      | rest j => exact related j

end S_zeluto

#print axioms S_zeluto.solved_bridge
