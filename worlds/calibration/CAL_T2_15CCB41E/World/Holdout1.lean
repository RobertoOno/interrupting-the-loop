import World.Base

namespace P3.CAL_T2_15CCB41E

def holdout1Term {α : Type} (a b c d e f : α) : Q_jabika α :=
  .q_dituca (.q_cobize a)
    (.q_dituca (.q_dituca (.q_cobize b) (.q_cobize c))
      (.q_dituca (.q_cobize d) (.q_dituca (.q_cobize e) (.q_cobize f))))

def Holdout1Statement : Prop :=
  ∀ (α β : Type) (encode : α → β)
    (opA : α → α → α) (opB : β → β → β),
    q_dowole encode opA opB →
    ∀ (a b c d e f : α),
      encode (q_zawasi opA (holdout1Term a b c d e f)) =
        q_zawasi opB (q_docecu encode (holdout1Term a b c d e f))

end P3.CAL_T2_15CCB41E
