// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title SimplePool
 * @dev minimal liquidity pool for testing the indexer.
 *
 * emits the same events as a real AMM pool (Deposit, Withdraw, Swap)
 * so we can test indexing without needing a mainnet fork.
 */

interface IERC20 {
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function transfer(address to, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}

contract SimplePool {
    IERC20 public token0;
    IERC20 public token1;

    uint256 public reserve0;
    uint256 public reserve1;
    uint256 public feeRate = 30; // 0.3% in basis points

    mapping(address => uint256) public liquidity;
    uint256 public totalLiquidity;

    event Deposit(address indexed provider, uint256 amount0, uint256 amount1, uint256 shares);
    event Withdraw(address indexed provider, uint256 amount0, uint256 amount1, uint256 shares);
    event Swap(
        address indexed sender,
        address tokenIn,
        uint256 amountIn,
        address tokenOut,
        uint256 amountOut,
        uint256 fee
    );

    constructor(address _token0, address _token1) {
        token0 = IERC20(_token0);
        token1 = IERC20(_token1);
    }

    function deposit(uint256 amount0, uint256 amount1) external returns (uint256 shares) {
        token0.transferFrom(msg.sender, address(this), amount0);
        token1.transferFrom(msg.sender, address(this), amount1);

        if (totalLiquidity == 0) {
            shares = sqrt(amount0 * amount1);
        } else {
            uint256 share0 = (amount0 * totalLiquidity) / reserve0;
            uint256 share1 = (amount1 * totalLiquidity) / reserve1;
            shares = share0 < share1 ? share0 : share1;
        }

        liquidity[msg.sender] += shares;
        totalLiquidity += shares;
        reserve0 += amount0;
        reserve1 += amount1;

        emit Deposit(msg.sender, amount0, amount1, shares);
    }

    function withdraw(uint256 shares) external returns (uint256 amount0, uint256 amount1) {
        require(liquidity[msg.sender] >= shares, "insufficient liquidity");

        amount0 = (shares * reserve0) / totalLiquidity;
        amount1 = (shares * reserve1) / totalLiquidity;

        liquidity[msg.sender] -= shares;
        totalLiquidity -= shares;
        reserve0 -= amount0;
        reserve1 -= amount1;

        token0.transfer(msg.sender, amount0);
        token1.transfer(msg.sender, amount1);

        emit Withdraw(msg.sender, amount0, amount1, shares);
    }

    function swap(address tokenIn, uint256 amountIn) external returns (uint256 amountOut) {
        require(
            tokenIn == address(token0) || tokenIn == address(token1),
            "invalid token"
        );

        bool isToken0 = tokenIn == address(token0);
        (IERC20 inToken, IERC20 outToken, uint256 resIn, uint256 resOut) = isToken0
            ? (token0, token1, reserve0, reserve1)
            : (token1, token0, reserve1, reserve0);

        inToken.transferFrom(msg.sender, address(this), amountIn);

        uint256 fee = (amountIn * feeRate) / 10000;
        uint256 amountInAfterFee = amountIn - fee;

        // constant product
        amountOut = (resOut * amountInAfterFee) / (resIn + amountInAfterFee);

        outToken.transfer(msg.sender, amountOut);

        if (isToken0) {
            reserve0 += amountIn;
            reserve1 -= amountOut;
        } else {
            reserve1 += amountIn;
            reserve0 -= amountOut;
        }

        emit Swap(msg.sender, tokenIn, amountIn, address(outToken), amountOut, fee);
    }

    function sqrt(uint256 x) internal pure returns (uint256) {
        if (x == 0) return 0;
        uint256 z = (x + 1) / 2;
        uint256 y = x;
        while (z < y) {
            y = z;
            z = (x / z + z) / 2;
        }
        return y;
    }
}
