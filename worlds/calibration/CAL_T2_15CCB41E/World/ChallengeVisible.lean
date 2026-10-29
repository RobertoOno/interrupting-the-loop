import World.Base

namespace P3.CAL_T2_15CCB41E

def visibleTerm {α : Type} (a b c d e : α) : Q_jabika α :=
  .q_dituca (.q_dituca (.q_cobize a) (.q_dituca (.q_cobize b) (.q_cobize c)))
    (.q_dituca (.q_cobize d) (.q_cobize e))

def VisibleStatement : Prop :=
  ∀ (α β : Type) (encode : α → β)
    (opA : α → α → α) (opB : β → β → β),
    q_dowole encode opA opB →
    ∀ (a b c d e : α),
      encode (q_zawasi opA (visibleTerm a b c d e)) =
        q_zawasi opB (q_docecu encode (visibleTerm a b c d e))

end P3.CAL_T2_15CCB41E
