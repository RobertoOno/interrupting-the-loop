import World.Base

namespace P3.DEV_INVARIANT_V3

def Holdout1Statement : Prop :=
  ∀ (a b : Int), ¬ Reaches start ⟨a, b, -a⟩

end P3.DEV_INVARIANT_V3
