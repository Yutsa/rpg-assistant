(ns rpg-assistant-web.views.section-tree)

(defn- build-tree [sections]
  (let [by-id (volatile! (into {} (map (fn [s] [(:id s) (assoc s :children [])]) sections)))
        root-ids (volatile! [])]
    (doseq [section sections]
      (let [node (get @by-id (:id section))
            parent-id (:parent_section_id section)]
        (if (and parent-id (contains? @by-id parent-id))
          (vswap! by-id update-in [parent-id :children] conj node)
          (vswap! root-ids conj (:id section)))))
    (map #(get @by-id %) @root-ids)))

(defn- section-branch [node selected-id]
  [:li {:key (:id node)}
   [:button {:class (when (= selected-id (:id node)) "active")
             :style {:padding-left (str (+ 0.75 (* (- (:level node) 1) 0.75)) "rem")}
             :on {:click [[:select-section (:id node)]]}}
    (:title node)
    [:span.pages
     (str "p." (:page_start node)
          (when (not= (:page_end node) (:page_start node))
            (str "–" (:page_end node))))]]
   (when (seq (:children node))
     [:ul
      (for [child (:children node)]
        (section-branch child selected-id))])])

(defn section-tree-view [sections selected-id]
  (let [tree (build-tree sections)]
    (if (empty? tree)
      [:p.muted {:style {:padding "1rem"}} "Aucune section."]
      [:nav.section-tree {:aria-label "Sections"}
       [:ul
        (for [node tree]
          (section-branch node selected-id))]])))
