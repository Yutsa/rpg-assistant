(ns rpg-assistant.web.components.section-tree
  (:require [uix.core :refer [defui $]]))

(defn- to-clj-section [^js s]
  {:id (.-id s)
   :parent_section_id (.-parent_section_id s)
   :title (.-title s)
   :level (.-level s)
   :page_start (.-page_start s)
   :page_end (.-page_end s)})

(defn- build-tree [sections]
  (let [items (mapv to-clj-section sections)
        by-parent (group-by :parent_section_id items)]
    (letfn [(attach [section]
              (assoc section :children (mapv attach (get by-parent (:id section) []))))]
      (mapv attach (get by-parent nil [])))))

(defui section-branch
  [{:keys [node selected-id on-select]}]
  ($ :li
    ($ :button {:type "button"
                :class (when (= selected-id (:id node)) "active")
                :style #js {:paddingLeft (str (+ 0.75 (* (- (:level node) 1) 0.75)) "rem")}
                :on-click #(on-select (:id node))}
      (:title node)
      ($ :span.pages
        (str "p." (:page_start node)
             (when (not= (:page_end node) (:page_start node))
               (str "–" (:page_end node))))))
    (when (seq (:children node))
      ($ :ul
        (for [child (:children node)]
          ($ section-branch {:key (:id child)
                             :node child
                             :selected-id selected-id
                             :on-select on-select}))))))

(defui section-tree
  [{:keys [sections selected-id on-select]}]
  (let [tree (build-tree sections)]
    (if (empty? tree)
      ($ :p.muted {:style #js {:padding "1rem"}} "Aucune section.")
      ($ :nav.section-tree {:aria-label "Sections"}
        ($ :ul
          (for [node tree]
            ($ section-branch {:key (:id node)
                               :node node
                               :selected-id selected-id
                               :on-select on-select})))))))
