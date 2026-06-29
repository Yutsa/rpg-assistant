(ns rpg.ingest.stat-blocks.schema)

(def BlockRef
  [:map
   [:page-number pos-int?]
   [:block-index int?]])

(def StatAbility
  [:map
   [:title string?]
   [:text string?]])

(def StatAttack
  [:map
   [:name string?]
   [:attack-bonus int?]
   [:damage string?]])

(def RulebookReference
  [:map
   [:profile-name string?]
   [:source-label {:optional true} string?]])

(def ParsedStatBlock
  [:map
   [:name string?]
   [:subtitle {:optional true} [:maybe string?]]
   [:nc {:optional true} [:maybe [:or string? int?]]]
   [:attributes {:optional true} [:map-of keyword? int?]]
   [:defense {:optional true} [:maybe int?]]
   [:vigor {:optional true} [:maybe int?]]
   [:initiative {:optional true} [:maybe int?]]
   [:mana {:optional true} [:maybe int?]]
   [:attacks {:optional true} [:sequential StatAttack]]
   [:abilities {:optional true} [:sequential StatAbility]]
   [:rulebook-reference {:optional true} [:maybe RulebookReference]]
   [:raw-text {:optional true} string?]
   [:block-refs {:optional true} [:sequential BlockRef]]
   [:game-system {:optional true} string?]])

(def StatBlockSpan
  [:map
   [:id string?]
   [:blocks sequential?]
   [:page-start pos-int?]
   [:page-end pos-int?]])
