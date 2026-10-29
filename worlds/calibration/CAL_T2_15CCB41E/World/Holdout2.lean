import World.Base

namespace P3.CAL_T2_15CCB41E

def holdout2Term {α : Type} (a b c d e f g : α) : Q_jabika α :=
  .q_dituca
    (.q_dituca (.q_dituca (.q_cobize a) (.q_cobize b)) (.q_cobize c))
    (.q_dituca (.q_cobize d) (.q_dituca (.q_cobize e) (.q_dituca (.q_cobize f) (.q_cobize g))))

def Holdout2Statement : Prop :=
  ∀ (α β : Type) (encode : α → β)
    (opA : α → α → α) (opB : β → β → β),
    q_dowole encode opA opB →
    ∀ (a b c d e f g : α),
      encode (q_zawasi opA (holdout2Term a b c d e f g)) =
        q_zawasi opB (q_docecu encode (holdout2Term a b c d e f g))

end P3.CAL_T2_15CCB41E
