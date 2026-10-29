import World.Base

namespace P3.DEV_INVARIANT_V3

def Holdout2Statement : Prop :=
  ∀ (a : Int), ¬ Reaches start ⟨a, a, a⟩

end P3.DEV_INVARIANT_V3
