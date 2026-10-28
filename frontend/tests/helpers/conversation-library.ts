function isHiddenByAncestor(element: Element): boolean {
  let current: Element | null = element
  while (current) {
    if (current.hasAttribute('hidden') || current.getAttribute('aria-hidden') === 'true') return true
    if (current.tagName === 'DETAILS' && !(current as HTMLDetailsElement).open) return true
    current = current.parentElement
  }
  return false
}

export function conversationButton(root: ParentNode, title: string): HTMLButtonElement {
  const buttons = Array.from(root.querySelectorAll<HTMLButtonElement>('.conversation-library-item, .conversation-library-table-select'))
  const matching = buttons.filter(button => button.querySelector('strong')?.textContent?.trim() === title)
  const selected = matching.find(button => !isHiddenByAncestor(button)) ?? matching[0]
  if (!selected) throw new Error(`No conversation row found for "${title}".`)
  return selected
}

export function conversationLibrary(root: ParentNode, title?: string): HTMLElement {
  const libraries = Array.from(root.querySelectorAll<HTMLElement>('.conversation-library'))
  const matching = libraries.filter(library => !isHiddenByAncestor(library)
    && (!title || Array.from(library.querySelectorAll('strong')).some(label => label.textContent?.trim() === title)))
  const selected = matching[0] ?? libraries.find(library => !isHiddenByAncestor(library)) ?? libraries[0]
  if (!selected) throw new Error('No conversation library was rendered.')
  return selected
}
