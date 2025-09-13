import { cn } from '@/lib/utils'

describe('cn utility function', () => {
  it('merges class names correctly', () => {
    expect(cn('class1', 'class2')).toBe('class1 class2')
  })

  it('handles conditional classes', () => {
    expect(cn('base', true && 'conditional', false && 'hidden')).toBe('base conditional')
  })

  it('merges conflicting Tailwind classes', () => {
    expect(cn('px-2 px-4')).toBe('px-4')
    expect(cn('bg-red-500 bg-blue-500')).toBe('bg-blue-500')
  })

  it('handles undefined and null values', () => {
    expect(cn('base', undefined, null, 'valid')).toBe('base valid')
  })

  it('handles empty strings', () => {
    expect(cn('base', '', 'valid')).toBe('base valid')
  })

  it('handles objects with conditional classes', () => {
    expect(cn('base', { 'conditional': true, 'hidden': false })).toBe('base conditional')
  })

  it('handles arrays of classes', () => {
    expect(cn('base', ['array1', 'array2'])).toBe('base array1 array2')
  })

  it('handles mixed input types', () => {
    expect(cn('base', 'string', { 'object': true }, ['array'])).toBe('base string object array')
  })

  it('handles no arguments', () => {
    expect(cn()).toBe('')
  })

  it('handles single argument', () => {
    expect(cn('single')).toBe('single')
  })
})
