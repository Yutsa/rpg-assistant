(ns rpg.ingest.stat-blocks.schema)

(def BlockRef
  [:map
   [:page-number pos-int?]
   [:block-index int?]])

(def StatAbility
  [:map
   [:title string?]
   [:text string?]])

(def RulebookReference
  [:map
   [:profile-name string?]
   [:source-label {:optional true} string?]])

(def ParsedStatBlock
  [:map
   [:name string?]
   [:subtitle {:optional true} [:maybe string?]]
   [:nc {:optional true} [:maybe int?]]
   [:attributes {:optional true} [:map-of keyword? int?]]
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
