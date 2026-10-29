namespace S_xeyiqa

universe u v

inductive Q_vuyixu (α : Type u) where
  | q_xiluhu : α → Q_vuyixu α
  | q_vozasa : Q_vuyixu α → Q_vuyixu α → Q_vuyixu α

def q_lohoyo {α : Type u} {β : Type v} (f : α → β) : Q_vuyixu α → Q_vuyixu β
  | .q_xiluhu x => .q_xiluhu (f x)
  | .q_vozasa left right => .q_vozasa (q_lohoyo f left) (q_lohoyo f right)

def q_mipote {α : Type u} (op : α → α → α) : Q_vuyixu α → α
  | .q_xiluhu x => x
  | .q_vozasa left right => op (q_mipote op left) (q_mipote op right)

def q_tedozi {α : Type u} {β : Type v}
    (encode : α → β) (opA : α → α → α) (opB : β → β → β) : Prop :=
  ∀ (x y : α), encode (opA x y) = opB (encode x) (encode y)

theorem solved_bridge {α : Type u} {β : Type v}
    (encode : α → β) (opA : α → α → α) (opB : β → β → β)
    (h : q_tedozi encode opA opB) :
    ∀ t : Q_vuyixu α,
      encode (q_mipote opA t) = q_mipote opB (q_lohoyo encode t) := by
  intro t
  induction t with
  | q_xiluhu x => rfl
  | q_vozasa left right ihLeft ihRight =>
      simp only [q_mipote, q_lohoyo]
      rw [h, ihLeft, ihRight]

#print axioms solved_bridge

end S_xeyiqa
