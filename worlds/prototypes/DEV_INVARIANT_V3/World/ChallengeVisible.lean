import World.Base

namespace P3.DEV_INVARIANT_V3

def VisibleStatement : Prop :=
  ∀ (b c : Int), ¬ Reaches start ⟨0, b, c⟩

end P3.DEV_INVARIANT_V3
