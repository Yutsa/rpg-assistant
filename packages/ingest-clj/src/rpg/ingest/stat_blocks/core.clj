(ns rpg.ingest.stat-blocks.core
  "Multimethod dispatch for stat block profiles.")

(defmulti detect-spans (fn [profile-id _pages] profile-id))
(defmulti parse-span (fn [profile-id _span] profile-id))
(defmulti false-heading? (fn [profile-id _block _page-blocks _idx _page] profile-id))
(defmulti matches-document? (fn [profile-id _pages] profile-id))
(defmulti normalize-block-text (fn [profile-id _text] profile-id))
(defmulti chunk-type-hint (fn [profile-id _text _blocks] profile-id))

(defn annotate-stat-blocks
  "Detect stat block spans and annotate page blocks in place (immutable update)."
  [profile-id pages]
  (let [{:keys [pages spans]} (detect-spans profile-id pages)]
    {:pages pages
     :spans spans
     :profile-id profile-id}))

(defn profile-false-heading?
  [profile-id block page-blocks idx page]
  (or (#{"header" "stats" "icon"} (get-in block [:metadata :stat-block-role]))
      (false-heading? profile-id block page-blocks idx page)))

(defn stat-block-block?
  [block]
  (boolean (get-in block [:metadata :stat-block-id])))
