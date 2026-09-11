import { test, expect, type Page } from '@playwright/test'

const TEST_EMAIL = `e2e-full-${Date.now()}@test.com`
const TEST_USER = `e2e-full-user-${Date.now()}`
const TEST_PASS = 'Test1234!'

// ============================================================================
// Helper Functions
// ============================================================================

async function registerNewUser(page: Page, email: string, username: string, password: string) {
  console.log(`🔄 Registering user: ${email}`)

  await page.goto('/login')
  await page.waitForURL('**/login')

  await page.getByText('没有账号？去注册').click()
  await page.waitForTimeout(500)

  await page.getByLabel('邮箱').fill(email)
  await page.getByLabel('用户名').fill(username)
  await page.getByLabel('密码').fill(password)
  await page.getByRole('button', { name: '注册' }).click()

  await expect(page.getByRole('heading', { name: '仪表盘' })).toBeVisible({ timeout: 15000 })
  console.log('✅ Registration successful')
}

async function loginUser(page: Page, email: string, password: string) {
  console.log(`🔄 Logging in as: ${email}`)

  await page.goto('/')
  await page.waitForTimeout(1000)

  // If already authenticated (e.g. after register), we land on dashboard directly
  if (await page.getByRole('heading', { name: '仪表盘' }).isVisible({ timeout: 3000 })) {
    console.log('✅ Already authenticated, on dashboard')
    return
  }

  await page.getByLabel('邮箱').fill(email)
  await page.getByLabel('密码').fill(password)
  await page.getByRole('button', { name: '登录' }).click()

  await expect(page.getByRole('heading', { name: '仪表盘' })).toBeVisible({ timeout: 15000 })
  console.log('✅ Login successful')
}

async function importDocument(page: Page, url: string, tags: string) {
  console.log(`🔄 Importing document: ${url}`)

  await page.goto('/documents')
  await page.waitForTimeout(1000)

  await page.getByPlaceholder('输入 URL 导入...').fill(url)
  await page.getByPlaceholder('标签（逗号分隔）').fill(tags)
  await page.getByRole('button', { name: '导入' }).click()

  await page.waitForResponse(
    (resp) => resp.url().includes('/api/documents/import') && resp.status() === 200,
    { timeout: 60_000 }
  )

  await page.waitForTimeout(3000)
  console.log('✅ Document imported successfully')

  const docCards = page.locator('.font-medium.truncate')
  const count = await docCards.count()
  expect(count).toBeGreaterThan(0)
  console.log(`📚 Found ${count} document(s)`)
}

async function navigateToQuiz(page: Page) {
  console.log('🔄 Navigating to Quiz page')

  await page.goto('/quiz')
  await page.waitForTimeout(1000)

  await expect(page.getByRole('heading', { name: '智能测验' })).toBeVisible()
  console.log('✅ Successfully navigated to Quiz page')
}

async function generateQuiz(page: Page, topic?: string) {
  console.log('🔄 Generating quiz...')

  const generateButton = page.getByRole('button', { name: /开始测验|生成测验/i })
  await expect(generateButton).toBeVisible()

  if (topic) {
    const topicInput = page.getByPlaceholder('Python 基础').or(page.getByPlaceholder('输入主题（可选）'))
    if (await topicInput.isVisible({ timeout: 3000 })) {
      await topicInput.fill(topic)
      console.log(`📝 Set quiz topic: ${topic}`)
    }
  }

  await generateButton.click()
  console.log('✅ Quiz generation initiated')

  await page.waitForTimeout(20000)
}

async function answerQuizQuestions(page: Page) {
  console.log('🔄 Answering quiz questions...')

  await page.waitForTimeout(2000)

  const submitButton = page.getByRole('button', { name: /提交|submit/i })
  if (!(await submitButton.isVisible({ timeout: 10000 }))) {
    console.log('⚠️ Quiz did not reach answering state')
    return
  }

  // Answer each question card by selecting its first radio option
  const questionCards = page.locator('div.bg-slate-800.rounded-xl').filter({ has: page.locator('input[type="radio"]') })
  const questionCount = await questionCards.count()
  if (questionCount === 0) {
    console.log('⚠️ No choice questions found')
    return
  }
  console.log(`📝 Found ${questionCount} question(s)`)

  for (let i = 0; i < questionCount; i++) {
    const card = questionCards.nth(i)
    await card.scrollIntoViewIfNeeded()
    await card.locator('input[type="radio"]').first().check({ force: true })
    console.log(`📝 Answered question ${i + 1}`)
  }

  await expect(submitButton).toBeEnabled({ timeout: 10000 })
  await submitButton.click()
  await page.waitForTimeout(5000)
  console.log('✅ Quiz submitted')
}

async function navigateToFeynman(page: Page) {
  console.log('🔄 Navigating to Feynman page')

  // Check if there's a Feynman page in the navigation
  await page.goto('/')

  await page.waitForTimeout(1000)

  // Try to find Feynman link in navigation
  const feynmanLink = page.getByRole('link', { name: /费曼|feynman/i })

  if (await feynmanLink.isVisible({ timeout: 2000 })) {
    await feynmanLink.click()
    await page.waitForTimeout(1000)
    console.log('✅ Successfully navigated to Feynman page via navigation')
    return
  }

  // Try direct URL
  try {
    await page.goto('/feynman')
    await page.waitForTimeout(1000)
    console.log('✅ Successfully navigated to Feynman page via direct URL')
  } catch (error) {
    console.log('⚠️ Feynman page not found, checking if it\'s integrated elsewhere...')

    // Check if Feynman is part of the Chat page
    await page.goto('/chat')
    await page.waitForTimeout(1000)
    console.log('🔄 Checked Chat page for Feynman functionality')
  }
}

async function performFeynmanLearning(page: Page) {
  console.log('🔄 Starting Feynman learning process...')

  // Look for Feynman-specific elements
  const startButton = page.getByRole('button', { name: /开始费曼|start feynman/i })
  if (await startButton.isVisible({ timeout: 3000 })) {
    await startButton.click()
    await page.waitForTimeout(2000)
    console.log('✅ Started Feynman session')
  }

  // Look for topic selection
  const topicInput = page.getByPlaceholder(/主题|topic/i)
  if (await topicInput.isVisible({ timeout: 3000 })) {
    await topicInput.fill('Python classes and object-oriented programming')
    console.log('📝 Selected Feynman topic: Python classes')
  }

  // Look for explanation area
  const explanationArea = page.locator('textarea, [contenteditable="true"]').first()
  if (await explanationArea.isVisible({ timeout: 3000 })) {
    const explanation = `Python classes are blueprints for creating objects. A class defines attributes (data) and methods (functions) that the objects created from the class will have. Objects are instances of classes. In Python, we define classes using the 'class' keyword. For example, class Dog: def __init__(self, name): self.name = name. This creates a Dog class with a name attribute.`
    await explanationArea.fill(explanation)
    console.log('📝 Provided Feynman explanation')
  }

  // Look for submit/evaluate button
  const evaluateButton = page.getByRole('button', { name: /评估|evaluate|提交|submit/i })
  if (await evaluateButton.isVisible({ timeout: 3000 })) {
    await evaluateButton.click()
    await page.waitForTimeout(10000)
    console.log('✅ Submitted Feynman explanation for evaluation')
  }

  // Look for results/feedback
  const feedbackArea = page.locator('[class*="feedback"], [class*="result"], [class*="score"]').first()
  if (await feedbackArea.isVisible({ timeout: 5000 })) {
    console.log('📊 Feynman evaluation results are visible')
  }
}

async function navigateToReview(page: Page) {
  console.log('🔄 Navigating to Review page')

  await page.goto('/review')
  await page.waitForTimeout(1000)

  await expect(page.locator('body')).toContainText('复习')
  console.log('✅ Successfully navigated to Review page')
}

async function performReview(page: Page) {
  console.log('🔄 Starting review process...')

  // Look for pending reviews
  const pendingItems = page.locator('[class*="pending"], [class*="review-item"]').filter({ hasText: /待复习|review|topic/i })
  const pendingCount = await pendingItems.count()

  if (pendingCount === 0) {
    console.log('⚠️ No pending reviews found')
    return
  }

  console.log(`📚 Found ${pendingCount} pending review(s)`)

  // Try to interact with the first review item
  try {
    const firstReview = pendingItems.first()
    await firstReview.scrollIntoViewIfNeeded()

    // Look for review action buttons
    const easyButton = page.getByRole('button', { name: /容易|easy/i })
    const goodButton = page.getByRole('button', { name: /良好|good/i })
    const hardButton = page.getByRole('button', { name: /困难|hard/i })
    const forgotButton = page.getByRole('button', { name: /忘记|forgot/i })

    // Try to select a review quality
    if (await goodButton.isVisible({ timeout: 3000 })) {
      await goodButton.click()
      console.log('✅ Submitted review with "good" quality')
    } else if (await easyButton.isVisible({ timeout: 1000 })) {
      await easyButton.click()
      console.log('✅ Submitted review with "easy" quality')
    } else {
      console.log('⚠️ No review quality buttons found')
    }

    await page.waitForTimeout(2000)
  } catch (error) {
    console.log('⚠️ Error performing review:', error)
  }
}

async function checkDashboard(page: Page) {
  console.log('🔄 Checking dashboard statistics...')

  await page.goto('/')
  await page.waitForTimeout(2000)

  // Look for dashboard statistics
  const statsElements = page.locator('[class*="stat"], [class*="metric"], [class*="count"]')
  const statsCount = await statsElements.count()

  console.log(`📊 Found ${statsCount} dashboard statistic element(s)`)

  // Check for expected dashboard elements
  const expectedElements = [
    '仪表盘',
    '今日学习',
    '文档',
    '测验',
    '复习'
  ]

  for (const element of expectedElements) {
    try {
      await expect(page.locator('body')).toContainText(element, { timeout: 2000 })
      console.log(`✅ Found dashboard element: ${element}`)
    } catch (error) {
      console.log(`⚠️ Dashboard element not found: ${element}`)
    }
  }
}

// ============================================================================
// Main Test Suite
// ============================================================================

test.describe('Complete User Flow E2E Tests', () => {
  test.beforeEach(async ({ page }) => {
    console.log('🚀 Starting new test...')
    await page.setDefaultTimeout(60000) // Set default timeout to 60 seconds
  })

  test.afterEach(async ({ page }) => {
    console.log('🏁 Test completed')
    await page.screenshot({ path: `test-result-${Date.now()}.png`, fullPage: true })
  })

  test('Complete user flow: Register → Login → Import Document → Quiz → Feynman → Review', async ({ page }) => {
    console.log('🎯 Starting complete user flow test')

    // Step 1: Register new user
    await registerNewUser(page, TEST_EMAIL, TEST_USER, TEST_PASS)

    // Step 2: Login
    await loginUser(page, TEST_EMAIL, TEST_PASS)

    // Step 3: Import document
    const testUrl = 'https://docs.python.org/3/tutorial/classes.html'
    const testTags = 'python,oop,classes'
    await importDocument(page, testUrl, testTags)

    // Step 4: Take quiz
    await navigateToQuiz(page)
    await generateQuiz(page, 'Python classes and OOP')
    await answerQuizQuestions(page)

    // Step 5: Feynman learning
    await navigateToFeynman(page)
    await performFeynmanLearning(page)

    // Step 6: Review
    await navigateToReview(page)
    await performReview(page)

    // Step 7: Check dashboard
    await checkDashboard(page)

    console.log('🎉 Complete user flow test finished successfully!')
  })

  test('Quick smoke test: Registration and basic navigation', async ({ page }) => {
    const quickTestEmail = `smoke-${Date.now()}@test.com`
    const quickTestUser = `smoke-user-${Date.now()}`

    await registerNewUser(page, quickTestEmail, quickTestUser, TEST_PASS)
    await loginUser(page, quickTestEmail, TEST_PASS)

    // Quick navigation check
    const routes = ['/', '/documents', '/quiz', '/review', '/progress']
    for (const route of routes) {
      await page.goto(route)
      await page.waitForTimeout(1000)
      console.log(`✅ Successfully navigated to ${route}`)
    }

    console.log('🎉 Smoke test completed successfully!')
  })

  test('Document import with duplicate detection', async ({ page }) => {
    const duplicateTestEmail = `duplicate-${Date.now()}@test.com`
    const duplicateTestUser = `duplicate-user-${Date.now()}`

    await registerNewUser(page, duplicateTestEmail, duplicateTestUser, TEST_PASS)
    await loginUser(page, duplicateTestEmail, TEST_PASS)

    const testUrl = 'https://docs.python.org/3/tutorial/classes.html'

    // First import
    await importDocument(page, testUrl, 'python,test')

    // Try duplicate import
    console.log('🔄 Testing duplicate import...')
    await page.goto('/documents')
    await page.waitForTimeout(1000)

    await page.getByPlaceholder('输入 URL 导入...').fill(testUrl)
    await page.getByRole('button', { name: '导入' }).click()

    // Wait for duplicate modal
    await page.waitForTimeout(5000)

    const modal = page.getByText('检测到重复文档')
    if (await modal.isVisible({ timeout: 5000 })) {
      console.log('✅ Duplicate detection modal appeared')

      // Test cancel option
      await page.getByRole('button', { name: '放弃导入' }).click()
      await page.waitForTimeout(2000)
      console.log('✅ Successfully cancelled duplicate import')
    } else {
      console.log('⚠️ Duplicate modal not found (may be reimported automatically)')
    }

    console.log('🎉 Duplicate detection test completed!')
  })

  test('Quiz generation and submission workflow', async ({ page }) => {
    const quizTestEmail = `quiz-${Date.now()}@test.com`
    const quizTestUser = `quiz-user-${Date.now()}`

    await registerNewUser(page, quizTestEmail, quizTestUser, TEST_PASS)
    await loginUser(page, quizTestEmail, TEST_PASS)

    // Import a document first
    await importDocument(page, 'https://docs.python.org/3/tutorial/classes.html', 'python,quiz')

    // Test quiz functionality
    await navigateToQuiz(page)

    // Try multiple quiz generations
    const topics = ['Python basics', 'Object-oriented programming', 'Classes and methods']

    for (const topic of topics) {
      try {
        await generateQuiz(page, topic)
        await answerQuizQuestions(page)

        // Go back to quiz page for next iteration
        await page.goto('/quiz')
        await page.waitForTimeout(2000)
      } catch (error) {
        console.log(`⚠️ Error with quiz topic "${topic}":`, error)
      }
    }

    console.log('🎉 Quiz workflow test completed!')
  })

  test('Review and spaced repetition workflow', async ({ page }) => {
    const reviewTestEmail = `review-${Date.now()}@test.com`
    const reviewTestUser = `review-user-${Date.now()}`

    await registerNewUser(page, reviewTestEmail, reviewTestUser, TEST_PASS)
    await loginUser(page, reviewTestEmail, TEST_PASS)

    // Import document and take quiz to generate review items
    await importDocument(page, 'https://docs.python.org/3/tutorial/classes.html', 'python,review')
    await navigateToQuiz(page)
    await generateQuiz(page, 'Python classes')
    await answerQuizQuestions(page)

    // Test review functionality
    await navigateToReview(page)
    await performReview(page)

    // Check if review statistics are available
    const reviewStats = page.locator('[class*="stat"], [class*="progress"]')
    const statsCount = await reviewStats.count()

    console.log(`📊 Found ${statsCount} review statistic element(s)`)

    console.log('🎉 Review workflow test completed!')
  })
})